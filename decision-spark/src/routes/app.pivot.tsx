import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pivot")({
  component: PivotRedirect,
  head: () => ({ meta: [{ title: "Analyse — DécisioBI" }] }),
});

function PivotRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate({ to: "/app/dashboard", replace: true });
  }, [navigate]);
  return null;
}
