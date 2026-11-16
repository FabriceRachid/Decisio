import { createFileRoute, redirect } from "@tanstack/react-router";

/** L'analyse conversationnelle vit dans l'Assistant IA. */
export const Route = createFileRoute("/app/analyse")({
  beforeLoad: () => {
    throw redirect({ to: "/app/chatbot", search: { context: "", sourceId: "" } });
  },
});
