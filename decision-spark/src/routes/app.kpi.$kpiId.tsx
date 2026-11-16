import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/app/kpi/$kpiId")({
  component: KpiDetailRedirect,
  head: () => ({ meta: [{ title: "Détails KPI — DécisioBI" }] }),
});

function KpiDetailRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate({ to: "/app/dashboard", replace: true });
  }, [navigate]);
  return null;
}
