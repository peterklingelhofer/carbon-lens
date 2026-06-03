import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { section as sectionFn, card } from "../styles";

const section = sectionFn(900);

const tierBadge: Record<string, { bg: string; color: string }> = {
  free: { bg: "var(--gray-100, #f3f4f6)", color: "var(--gray-600)" },
  pro: { bg: "var(--green-100, #dcfce7)", color: "var(--green-700, #15803d)" },
  enterprise: { bg: "var(--blue-100, #dbeafe)", color: "var(--blue-700, #1d4ed8)" },
};

export function Organizations() {
  const queryClient = useQueryClient();
  const [newOrgName, setNewOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: orgs, isLoading, isError } = useQuery({
    queryKey: ["orgs"],
    queryFn: () => api.orgs.list(),
    retry: false,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => api.orgs.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
      setNewOrgName("");
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    createMutation.mutate(newOrgName.trim());
  }

  return (
    <div style={section}>
      <style>{`
        @media (max-width: 600px) {
          .org-create-form { flex-direction: column !important; }
          .org-card-row { flex-direction: column !important; align-items: stretch !important; gap: 0.75rem !important; }
        }
      `}</style>
      <h1 style={{ marginBottom: "0.5rem" }}>Organizations</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Manage your organizations and API keys.
      </p>

      {/* Create org form */}
      <div style={{ ...card, marginBottom: "2rem" }}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Create Organization</h2>
        <form onSubmit={handleCreate} className="org-create-form" style={{ display: "flex", gap: "0.75rem" }}>
          <input
            type="text"
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
            placeholder="Organization name"
            style={{
              flex: 1,
              padding: "0.6rem 0.75rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: "var(--surface)",
              color: "inherit",
              fontSize: "0.9rem",
            }}
          />
          <button
            type="submit"
            disabled={createMutation.isPending || !newOrgName.trim()}
            style={{
              padding: "0.6rem 1.5rem",
              borderRadius: 6,
              border: "none",
              background: "var(--green-500, #22c55e)",
              color: "white",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: createMutation.isPending ? "wait" : "pointer",
              opacity: !newOrgName.trim() ? 0.5 : 1,
            }}
          >
            {createMutation.isPending ? "Creating..." : "Create"}
          </button>
        </form>
        {error && (
          <p style={{ color: "var(--red-500, #ef4444)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {error}
          </p>
        )}
        <p style={{ color: "var(--gray-400)", fontSize: "0.8rem", marginTop: "0.5rem" }}>
          Requires admin secret in X-API-Key header. Set CARBON_LENS_ADMIN_SECRET in .env.
        </p>
      </div>

      {/* Org list */}
      {isLoading ? (
        <p style={{ color: "var(--gray-400)" }}>Loading organizations...</p>
      ) : isError ? (
        <div style={{ ...card, textAlign: "center", color: "var(--gray-400)" }}>
          <p style={{ marginBottom: "0.5rem" }}>Could not load organizations.</p>
          <p style={{ fontSize: "0.85rem" }}>
            Organizations require database mode and admin auth.
            Set <code>CARBON_LENS_USE_DATABASE=true</code> and <code>CARBON_LENS_ADMIN_SECRET</code>.
          </p>
        </div>
      ) : orgs && orgs.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {orgs.map((org) => {
            const badge = tierBadge[org.tier] || tierBadge.free;
            return (
              <div key={org.id} className="org-card-row" style={{ ...card, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "1.05rem", marginBottom: 4 }}>
                    {org.name}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--gray-500)", fontFamily: "var(--mono)" }}>
                    /{org.slug}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <span
                    style={{
                      padding: "0.2rem 0.75rem",
                      borderRadius: 12,
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      background: badge.bg,
                      color: badge.color,
                    }}
                  >
                    {org.tier}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ ...card, textAlign: "center", color: "var(--gray-400)" }}>
          No organizations yet. Create one above to get started.
        </div>
      )}
    </div>
  );
}
