import json
import logging
import re
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

from django.db.models import Q
from django.utils import timezone

from apps.chatbot.models import ChatMessage, ChatSession, QueryHistory
from apps.conflits.models import Conflict
from apps.kpi.models import KPIAlert
from apps.ia_interpretation.services import (
    KPIInterpretationError,
    build_kpi_context_for_user,
    build_kpi_context_by_source,
    build_data_context_for_source,
    interpret_kpis_with_groq,
    persist_ai_analysis,
    safe_json_dumps,
)


CHATBOT_SYSTEM_PROMPT = """Tu es Decisio AI, un analyste data intelligent et conversationnel pour une PME francophone.

## Ton rôle
Tu es un compagnon de données complet. L'utilisateur peut te parler de ses KPIs, de ses fichiers, de ses colonnes, de ses tendances, ou simplement discuter.

## Règles fondamentales
- Réponds en français clair, ton professionnel mais chaleureux.
- NE JAMAIS inventer de valeurs, de tendances ou de données non fournies.
- Si une info manque, dis-le explicitement.
- Structures tes réponses avec des titres Markdown (## Titre), des listes à puces, des tableaux.
- NE JAMAIS utiliser d'astérisques (*) pour la mise en forme.
- Sois concis mais complet. Va à l'essentiel.

## Tu reçois trois types de contexte

### 1. Données KPI (si disponibles)
Des KPIs avec leurs valeurs, breakdowns, historiques. Utilise-les pour :
- Expliquer les chiffres et leur signification business
- Détecter anomalies (variance > 20%, écarts target, tendances)
- Comparer les dimensions (régions, produits, etc.)
- Proposer des actions concrètes

### 2. Contexte d'un widget spécifique (si disponible)
Un widget précis avec sa mesure, agrégation, dimension et données.
Concentre-toi sur CE widget : explique les résultats, identifie forces/faiblesses, propose des actions.

### 3. Métadonnées de données brutes (si disponibles)
La structure du fichier : colonnes, types, échantillons. Utilise-les pour :
- Décrire ce que contient le fichier
- Expliquer ce que signifie chaque colonne
- Suggérer des analyses pertinentes
- Répondre à des questions comme "qu'est-ce que mon fichier contient ?"

## Comment répondre
- Question sur un KPI → analyse les chiffres fournis
- Demande d'expliquer une colonne → utilise les métadonnées et échantillons
- "Qu'est-ce que j'ai dans mes données ?" → décris la structure et le contenu
- Question générale → réponds avec les données disponibles
- Conseil demandé → recommandations actionnables
- Anomalie détectée → "Alerte" + impact business
"""

CHATBOT_DEFAULT_SUGGESTIONS = [
    'Quels KPI expliquent la baisse de marge ?',
    'Resume les alertes critiques de cette semaine.',
    'Quels indicateurs demandent une action immediate ?',
]

DOMAIN_SUGGESTIONS = {
    'dashboard': [
        'Quels indicateurs demandent une action immediate ?',
        'Resume les alertes critiques de cette semaine.',
        'Pourquoi la marge baisse ce mois-ci ?',
    ],
    'sales': [
        'Quels KPI expliquent la progression des ventes ?',
        'Quels canaux tirent le chiffre d affaires ?',
        'Ou perd-on de la marge commerciale ?',
    ],
    'stocks': [
        'Quelles references risquent une rupture ?',
        'Quels depots sont les plus tendus ?',
        'Quelles actions stock faut-il prioriser ?',
    ],
    'finance': [
        'Qu est-ce qui met la tresorerie sous pression ?',
        'Quels KPI expliquent la baisse de marge ?',
        'Quelles creances doivent etre traitees en premier ?',
    ],
    'clients': [
        'Quels clients concentrent le plus de risque ?',
        'Quels comptes structurent le revenu ?',
        'Quels signaux montrent un risque de churn ?',
    ],
    'regions': [
        'Quelles zones performent le mieux ?',
        'Ou sont les retards les plus eleves ?',
        'Compare les territoires les plus rentables.',
    ],
    'alerts': [
        'Quelle alerte KPI doit etre traitee en premier ?',
        'Quels conflits bloquent le dashboard ?',
        'Resume les alertes et risques critiques.',
    ],
}


def create_chat_session(*, user, **validated_data):
    return ChatSession.objects.create(
        user=user,
        session_token=secrets.token_urlsafe(24),
        bot_personality=validated_data.get('bot_personality') or 'professional',
        language_preference=validated_data.get('language_preference') or 'fr',
        session_name=validated_data.get('session_name') or None,
        channel=validated_data.get('channel'),
        referral_source=validated_data.get('referral_source'),
        context={'scope': 'assistant_decisionnel'},
        tags=['assistant', 'decisionnel'],
    )


def infer_query_type(content: str) -> str:
    lowered = content.lower()
    if any(keyword in lowered for keyword in ['kpi', 'marge', 'ca', 'chiffre', 'stock', 'tresorerie']):
        return 'kpi_query'
    if any(keyword in lowered for keyword in ['comment', 'pourquoi', 'explique']):
        return 'insight_request'
    return 'data_query'


def infer_intent(content: str) -> str:
    """Infer intent but NEVER short-circuit the LLM. All queries go through Groq."""
    lowered = content.lower()
    if any(keyword in lowered for keyword in ['detail', 'decomp', 'par region', 'par produit', 'par mois', 'par client', 'par categorie', 'par vendeur', 'par depot', 'par canal']):
        return 'DRILL_DOWN'
    if any(keyword in lowered for keyword in ['compare', 'compar', 'ecart', 'variation']):
        return 'COMPARE_PERFORMANCE'
    if any(keyword in lowered for keyword in ['kpi', 'marge', 'ca', 'chiffre', 'stock', 'tresorerie', 'alerte', 'anomalie', 'risque']):
        return 'QUERY_KPI'
    return 'ASK_DATA'


def extract_entities(content: str) -> dict:
    months = re.findall(r'\b(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\b', content.lower())
    return {
        'months': months,
        'contains_numeric_reference': bool(re.search(r'\d', content)),
    }


def infer_domain(*, content: str, context: Optional[dict]) -> str:
    page = ((context or {}).get('page') or '').lower()
    if page in DOMAIN_SUGGESTIONS:
        return page

    lowered = content.lower()
    if any(keyword in lowered for keyword in ['vente', 'commercial', 'canal', 'client']):
        return 'sales'
    if any(keyword in lowered for keyword in ['stock', 'rupture', 'depot', 'appro']):
        return 'stocks'
    if any(keyword in lowered for keyword in ['tresorerie', 'finance', 'marge', 'creance']):
        return 'finance'
    if any(keyword in lowered for keyword in ['region', 'territoire', 'agence', 'zone']):
        return 'regions'
    if any(keyword in lowered for keyword in ['alerte', 'anomalie', 'risque', 'conflit']):
        return 'alerts'
    return 'dashboard'


def build_contextual_question(*, question: str, context: Optional[dict], domain: str) -> str:
    context = context or {}
    fragments = []

    page_label = context.get('page_label')
    filter_label = context.get('filter_label')
    focus_label = context.get('focus_label')

    if page_label:
        fragments.append(f"Contexte ecran: {page_label}")
    if filter_label:
        fragments.append(f"Periode active: {filter_label}")
    if focus_label:
        fragments.append(f"Focus metier: {focus_label}")
    fragments.append(f"Domaine principal: {domain}")

    return f"{question.strip()}\n\nContexte metier:\n- " + "\n- ".join(fragments)


def _format_conversation_history(session, limit: int = 5) -> str:
    recent = session.messages.order_by('-created_at')[:limit]
    lines = []
    for msg in reversed(list(recent)):
        role = "Utilisateur" if msg.message_type == "user" else "Assistant"
        lines.append(f"[{role}] {msg.content[:200]}")
    return "\n".join(lines)


def _build_kpi_snapshot_payload(*, kpi_context: list[dict], domain: str, context: Optional[dict]):
    on_target = sum(1 for item in kpi_context if item.get('status') == 'on_target')
    warning = sum(1 for item in kpi_context if item.get('status') == 'warning')
    critical = sum(1 for item in kpi_context if item.get('status') == 'critical')

    focus_items = []
    for item in kpi_context[:4]:
        focus_items.append({
            'label': item.get('name'),
            'value': item.get('value'),
            'status': item.get('status'),
        })

    return {
        'summary_cards': [
            {'label': 'KPI analyses', 'value': len(kpi_context), 'tone': 'blue'},
            {'label': 'Sous controle', 'value': on_target, 'tone': 'green'},
            {'label': 'A surveiller', 'value': warning, 'tone': 'amber'},
            {'label': 'Critiques', 'value': critical, 'tone': 'red'},
        ],
        'focus_items': focus_items,
        'domain': domain,
        'context': context or {},
    }


def _build_fallback_response(*, question: str, domain: str, context: Optional[dict], kpi_context: Optional[list[dict]] = None, reason: Optional[str] = None) -> dict:
    kpi_context = kpi_context or []
    page_label = (context or {}).get('page_label')
    filter_label = (context or {}).get('filter_label')

    if kpi_context:
        top_kpi_lines = []
        for item in kpi_context[:4]:
            value = item.get('value')
            status = item.get('status') or 'unknown'
            label = item.get('name') or 'KPI'
            top_kpi_lines.append(f"- {label} : {value} ({status})")

        text = [
            "Constat principal : le moteur IA n est pas disponible pour le moment, donc je te donne une synthese heuristique sur les KPI visibles.",
        ]
        if page_label or filter_label:
            text.append(f"Contexte actif : {page_label or 'ecran non precise'} · {filter_label or 'periode non precisee'}.")
        text.append("KPI a surveiller en priorite :")
        text.extend(top_kpi_lines)
        text.append("Actions recommandees : verifier les KPI en statut warning/critical, puis ouvrir la vue detaillee du module associe avant de prendre une decision.")
    else:
        text = [
            "Constat principal : je n'ai pas assez de KPI exploitable dans cette conversation pour produire une analyse detaillee, je te propose donc une synthese heuristique.",
        ]
        if page_label or filter_label:
            text.append(f"Contexte actif : {page_label or 'ecran non precise'} · {filter_label or 'periode non precisee'}.")
        text.append("Actions recommandees : active des KPI sur le tableau de bord ou pose une question liee aux ventes, a la marge, au stock, a la tresorerie ou aux alertes.")

    if reason:
        text.append(f"Note technique : {reason}")

    return {
        'text': "\n\n".join(text),
        'model': 'chatbot-fallback',
        'tokens_used': 0,
        'processing_time_ms': 0,
        'fallback_used': True,
        'attached_data': _build_kpi_snapshot_payload(kpi_context=kpi_context, domain=domain, context=context),
        'suggested_questions': DOMAIN_SUGGESTIONS.get(domain) or CHATBOT_DEFAULT_SUGGESTIONS,
    }


def _build_alerts_snapshot(*, user):
    alert_qs = KPIAlert.objects.select_related('kpi').filter(is_active=True)
    conflict_qs = Conflict.objects.select_related('conflict_type', 'data_source')

    if not user.is_superuser:
        alert_qs = alert_qs.filter(Q(kpi__is_public=True) | Q(kpi__owner=user)).distinct()
        conflict_qs = conflict_qs.filter(data_source__uploaded_by=user)

    alerts = list(alert_qs.order_by('-last_triggered_at', '-created_at')[:5])
    conflicts = list(conflict_qs.order_by('-priority', '-detected_at')[:5])

    return {
        'alerts': [
            {
                'id': alert.id,
                'name': alert.alert_name,
                'kpi_name': alert.kpi.name,
                'alert_type': alert.alert_type,
                'trigger_count': alert.trigger_count,
                'is_triggered': alert.is_triggered,
                'last_triggered_at': alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
            }
            for alert in alerts
        ],
        'conflicts': [
            {
                'id': conflict.id,
                'description': conflict.description,
                'severity': conflict.conflict_type.severity,
                'priority': conflict.priority,
                'source_name': conflict.data_source.name,
                'status': conflict.status,
            }
            for conflict in conflicts
        ],
        'summary': {
            'active_alerts': len(alerts),
            'triggered_alerts': sum(1 for alert in alerts if alert.is_triggered),
            'open_conflicts': sum(1 for conflict in conflicts if conflict.status != 'resolved'),
            'critical_conflicts': sum(1 for conflict in conflicts if conflict.priority >= 9),
        },
    }


def _build_alert_response(question: str, snapshot: dict) -> dict:
    summary = snapshot['summary']
    alerts = snapshot['alerts']
    conflicts = snapshot['conflicts']

    lines = [
        f"Constat principal : {summary['triggered_alerts']} alerte(s) KPI sont actuellement declenchees et {summary['open_conflicts']} conflit(s) de donnees restent ouverts.",
    ]

    if alerts:
        top_alert = alerts[0]
        lines.append(
            f"Point d attention : l alerte '{top_alert['name']}' sur {top_alert['kpi_name']} reste la plus recente."
        )
    if conflicts:
        top_conflict = conflicts[0]
        lines.append(
            f"Risque donnees : conflit priorite {top_conflict['priority']} sur {top_conflict['source_name']} ({top_conflict['description']})."
        )

    lines.append("Actions recommandees : traiter d abord les alertes declenchees, puis resoudre les conflits de priorite elevee avant de revalider le dashboard.")

    return {
        'text': "\n\n".join(lines),
        'model': 'chatbot-alerts-heuristic',
        'tokens_used': None,
        'processing_time_ms': 0,
        'attached_data': snapshot,
        'suggested_questions': [
            'Quelle alerte KPI doit etre traitee en premier ?',
            'Quels conflits bloquent le plus la fiabilite du dashboard ?',
            'Resume les alertes et conflits critiques seulement.',
        ],
    }


def _extract_drill_dimension(content: str) -> Optional[str]:
    lowered = content.lower()
    dimensions = ['region', 'produit', 'client', 'categorie', 'vendeur', 'depot', 'canal', 'mois', 'trimestre', 'semestre', 'jour']
    for dim in dimensions:
        if dim in lowered:
            return dim
    return None


def _fetch_drill_down_data(user, dimension: str, kpi_context: list) -> list:
    enriched = []
    for kpi_item in kpi_context:
        breakdown = kpi_item.get('latest_calculation', {}).get('breakdown')
        if breakdown and isinstance(breakdown, list):
            drill_items = [b for b in breakdown if isinstance(b, dict) and b.get(dimension)]
            if drill_items:
                enriched.append({
                    'name': kpi_item.get('name'),
                    'dimension': dimension,
                    'breakdown': drill_items,
                })
    return enriched


def _run_assistant_engine(*, user, question: str, intent: str, domain: str, context: Optional[dict], model: Optional[str], session=None):
    """Run the assistant engine. ALL queries go through the LLM - no short-circuits."""
    contextual_question = build_contextual_question(question=question, context=context, domain=domain)

    source_id = (context or {}).get('source_id')
    widget_ids = (context or {}).get('widget_ids')
    widget_context_text = (context or {}).get('widget_context')

    kpi_context = []
    kpis = []
    try:
        if source_id:
            kpi_context = build_kpi_context_by_source(
                user=user,
                source_id=source_id,
                widget_ids=widget_ids,
                max_kpis=5,
            )
        else:
            kpi_context, kpis = build_kpi_context_for_user(user=user, max_kpis=5, enrichi=True)
    except KPIInterpretationError:
        kpi_context = []
    except Exception:
        logger.debug("KPI context build failed, continuing without KPIs")
        kpi_context = []

    data_context = None
    if source_id:
        try:
            data_context = build_data_context_for_source(source_id=source_id, max_sample_rows=2)
        except Exception:
            pass

    if intent == 'DRILL_DOWN':
        dimension = _extract_drill_dimension(question)
        if dimension:
            drill_data = _fetch_drill_down_data(user, dimension, kpi_context)
            if drill_data:
                contextual_question += f"\n\nDonnees detaillees pour la dimension '{dimension}' :\n{safe_json_dumps(drill_data, indent=2)}"

    conversation_history = None
    if session:
        conversation_history = _format_conversation_history(session, limit=5)

    try:
        result = interpret_kpis_with_groq(
            user=user,
            question=contextual_question,
            kpi_context=kpi_context,
            model=model,
            system_prompt=CHATBOT_SYSTEM_PROMPT,
            conversation_history=conversation_history,
            widget_context=widget_context_text,
            data_context=data_context,
        )
    except KPIInterpretationError as exc:
        result = _build_fallback_response(
            question=question,
            domain=domain,
            context=context,
            kpi_context=kpi_context,
            reason=str(exc),
        )

    result['suggested_questions'] = DOMAIN_SUGGESTIONS.get(domain) or CHATBOT_DEFAULT_SUGGESTIONS
    result['attached_data'] = result.get('attached_data') or _build_kpi_snapshot_payload(kpi_context=kpi_context, domain=domain, context=context)
    return result, kpi_context, kpis


def process_chat_message(*, session: ChatSession, user, content: str, persist_analysis: bool = True, model: Optional[str] = None, context: Optional[dict] = None):
    trimmed = content.strip()
    if not trimmed:
        raise KPIInterpretationError('Le message ne peut pas etre vide.')

    is_simple_greeting = _is_simple_message(trimmed)

    intent = infer_intent(trimmed)
    entities = extract_entities(trimmed)
    query_type = infer_query_type(trimmed)
    domain = infer_domain(content=trimmed, context=context)

    enriched_context = dict(context or {})
    if not enriched_context.get('widget_context'):
        context_str = enriched_context.get('context', '')
        if context_str and ('ANALYSE DU WIDGET' in context_str or 'Mesure:' in context_str):
            enriched_context['widget_context'] = context_str

    user_message = ChatMessage.objects.create(
        session=session,
        message_type='user',
        content_type='question',
        content=trimmed,
        intent=intent,
        entities=entities,
        sentiment='neutral',
        confidence=0.82,
    )

    analysis_id = None
    history = QueryHistory.objects.create(
        user=user,
        session=session,
        query_text=trimmed,
        query_type=query_type,
        parsed_intent=intent,
        extracted_entities=entities,
        nlp_confidence=0.82,
    )

    try:
        small_talk_category = _detect_small_talk(trimmed)
        if small_talk_category:
            result = _build_small_talk_response(category=small_talk_category, user=user, question=trimmed)
            kpi_context, kpis = [], []
        else:
            result, kpi_context, kpis = _run_assistant_engine(
                user=user,
                question=trimmed,
                intent=intent,
                domain=domain,
                context=enriched_context,
                model=model,
                session=session,
            )

        if persist_analysis and kpi_context is not None and not is_simple_greeting:
            try:
                primary = kpis[0] if len(kpis) == 1 else None
                analysis_id = persist_ai_analysis(
                    user=user,
                    question=trimmed,
                    kpi_context=kpi_context,
                    result=result,
                    primary_kpi=primary,
                )
            except Exception:
                logger.debug("Failed to persist AI analysis, continuing")

        bot_message = ChatMessage.objects.create(
            session=session,
            message_type='bot',
            content_type='insight',
            content=result['text'],
            intent=intent,
            attached_data={
                'analysis_id': analysis_id,
                'kpi_count': len(kpi_context or []),
                'domain': domain,
                'context': enriched_context,
                **(result.get('attached_data') or {}),
            },
            suggested_questions=result.get('suggested_questions') or CHATBOT_DEFAULT_SUGGESTIONS,
            response_time_ms=result.get('processing_time_ms'),
            model_used=result.get('model'),
            fallback_used=bool(result.get('fallback_used')),
        )

        history.execution_plan = {
            'orchestrator': 'chatbot',
            'engine': 'ia_interpretation',
            'kpi_count': len(kpi_context or []),
            'domain': domain,
            'context': enriched_context,
        }
        history.execution_time_ms = result.get('processing_time_ms')
        history.rows_returned = len(kpi_context or [])
        history.result_summary = result['text'][:1000]
        history.full_result = {
            'analysis_id': analysis_id,
            'model': result.get('model'),
            'tokens_used': result.get('tokens_used'),
        }
        history.was_successful = True
        history.save()

        session.message_count = session.messages.count()
        session.active_kpis = [item['id'] for item in (kpi_context or [])]
        session.context = {**(session.context or {}), **enriched_context, 'domain': domain, 'last_intent': intent}
        session.last_activity_at = timezone.now()

        update_fields = ['message_count', 'active_kpis', 'context', 'last_activity_at']
        if not session.session_name and session.message_count <= 1:
            session.session_name = trimmed[:80]
            update_fields.append('session_name')

        session.save(update_fields=update_fields)

        return {
            'session': session,
            'user_message': user_message,
            'bot_message': bot_message,
            'analysis_id': analysis_id,
        }
    except Exception as exc:
        try:
            history.was_successful = False
            history.error_message = str(exc)[:2000]
            history.requires_human = True
            history.save(update_fields=['was_successful', 'error_message', 'requires_human'])
        except Exception:
            pass
        raise


def _is_simple_message(text: str) -> bool:
    """Detect simple greetings or very short messages that don't need analysis persistence."""
    lowered = text.lower().strip()
    simple_patterns = [
        'bonjour', 'salut', 'hello', 'coucou', 'hey',
        'merci', 'ok', 'super', 'parfait', 'compris',
        'au revoir', 'bye', 'a plus', 'a bientot',
        'oui', 'non', 'peut-etre',
    ]
    if len(lowered) < 15 and any(lowered.startswith(p) for p in simple_patterns):
        return True
    return False


def _detect_small_talk(text: str) -> Optional[str]:
    """Detect conversational small talk and return a category:
    'greeting', 'identity', 'capabilities', 'thanks' or 'farewell'.
    Returns None when the message requires data analysis."""
    lowered = re.sub(r"[^a-z0-9éèêàçùôîûäöü\s]", ' ', text.lower())
    lowered = re.sub(r'\s+', ' ', lowered).strip()

    if re.match(r'^(bonjour|bonsoir|salut|hello|coucou|hey|yo|re)\b', lowered):
        return 'greeting'
    if re.match(r'^(merci|merci beaucoup|super|parfait|top|ok)\b', lowered):
        return 'thanks'
    if re.match(r'^(au revoir|bye|a bientot|a bientôt|a plus|bonne journee|bonne journée)\b', lowered):
        return 'farewell'
    if any(kw in lowered for kw in (
        'qui es tu', 'qui es-tu', 'tu es qui', 'qui tu es',
        'presente toi', 'présente toi', 'presente toi', 'cest quoi toi', 'c est quoi toi',
    )):
        return 'identity'
    if any(kw in lowered for kw in (
        'que fais tu', 'que fais-tu', 'quest ce que tu fais', 'qu est ce que tu fais',
        'qu est-ce que tu fais', 'que sais tu faire', 'que sais-tu faire',
        'tu peux faire quoi', 'tu sais faire quoi', 'tu peux faire',
        'que peux tu faire', 'qu est ce que tu sais faire', 'a quoi tu sers', 'à quoi tu sers',
        'quelle est ta mission', 'quel est ton role', 'quel est ton rôle',
    )):
        return 'capabilities'
    return None


SMALL_TALK_RESPONSES = {
    'greeting': (
        "Bonjour ! Je suis Decisio AI, votre analyste de données. "
        "Je peux analyser vos KPIs, expliquer vos indicateurs, détecter des anomalies ou vous aider à comprendre vos données. "
        "Posez-moi une question sur vos chiffres, par exemple : Quels KPI expliquent la baisse de marge ?"
    ),
    'thanks': (
        "Avec plaisir ! N'hésitez pas si vous voulez approfondir un chiffre, comparer des indicateurs "
        "ou préparer un rapport. Je suis là pour ça."
    ),
    'farewell': (
        "Au revoir ! Bonne journée. Revenez quand vous voulez analyser vos données, je serai là."
    ),
    'identity': (
        "Je suis Decisio AI, un assistant d'analyse de données conçu pour votre entreprise. "
        "Je m'appuie sur vos sources de données, vos KPIs et vos widgets pour vous aider à comprendre "
        "vos performances : tendances, anomalies, écarts aux objectifs. "
        "Je ne fabrique aucune donnée : tout ce que je vous dis vient de vos fichiers et indicateurs."
    ),
    'capabilities': (
        "Je peux vous aider sur plusieurs choses :\n"
        "- Analyser vos **KPIs** et expliquer leurs évolutions\n"
        "- **Détecter des anomalies** (variations, écarts aux objectifs)\n"
        "- Comparer des **dimensions** (régions, produits, clients...)\n"
        "- Décrire le **contenu d'un fichier** (colonnes, types, échantillons)\n"
        "- Résumer vos **alertes** et priorités\n\n"
        "Posez-moi une question sur vos données, par exemple : Quels KPI expliquent la baisse de marge ?"
    ),
}


def _build_small_talk_response(*, category: str, user, question: str) -> dict:
    text = SMALL_TALK_RESPONSES.get(category, SMALL_TALK_RESPONSES['capabilities'])
    return {
        'text': text,
        'model': 'decisio-ai',
        'tokens_used': 0,
        'processing_time_ms': 0,
        'fallback_used': False,
        'suggested_questions': CHATBOT_DEFAULT_SUGGESTIONS,
    }
