import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/app/kpi")({
  component: KpiRedirect,
  head: () => ({ meta: [{ title: "Indicateurs — DécisioBI" }] }),
});

function KpiRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate({ to: "/app/dashboard", replace: true });
  }, [navigate]);
  return null;
}
