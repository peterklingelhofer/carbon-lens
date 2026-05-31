import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { section as sectionFn } from "../styles";

const section = sectionFn(1000);

function formatPrice(cents: number): string {
  if (cents === 0) return "Free";
  return `$${(cents / 100).toFixed(0)}/mo`;
}

export function Plans() {
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: plans, isLoading } = useQuery({
    queryKey: ["plans"],
    queryFn: () => api.plans(),
  });

  const { data: billing } = useQuery({
    queryKey: ["billing-status"],
    queryFn: () => api.billingStatus(),
  });

  const tierColors: Record<string, string> = {
    Free: "var(--gray-600)",
    Pro: "var(--green-600)",
    Enterprise: "var(--blue-500)",
  };

  async function handleUpgrade(tier: string) {
    setUpgrading(tier);
    setError(null);
    try {
      const plan = tier.toLowerCase() as "pro" | "enterprise";
      // Uses the billing status org context; for now pass a placeholder
      // that the backend will resolve from the API key
      const { checkout_url } = await api.orgs.checkout("current", plan);
      window.location.assign(checkout_url);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upgrade failed";
      setError(msg);
      setUpgrading(null);
    }
  }

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem", textAlign: "center" }}>Plans & Pricing</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2.5rem", textAlign: "center" }}>
        Carbon data API + compliance reporting. Start free, scale to enterprise.
      </p>

      {error && (
        <div
          style={{
            background: "var(--red-50, #fef2f2)",
            border: "1px solid var(--red-200, #fecaca)",
            borderRadius: 8,
            padding: "0.75rem 1rem",
            marginBottom: "1.5rem",
            color: "var(--red-700, #b91c1c)",
            fontSize: "0.85rem",
            textAlign: "center",
          }}
        >
          {error}
        </div>
      )}

      {isLoading ? (
        <p style={{ textAlign: "center", color: "var(--gray-400)" }}>Loading plans...</p>
      ) : plans ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "1.5rem",
            alignItems: "start",
          }}
        >
          {plans.map((plan) => {
            const tierKey = plan.name.toLowerCase();
            const isCurrent = billing?.tier.toLowerCase() === tierKey;
            const canUpgrade = !isCurrent && tierKey !== "free";
            return (
              <div
                key={plan.name}
                style={{
                  background: "var(--card-bg)",
                  borderRadius: 12,
                  padding: "2rem",
                  border: isCurrent
                    ? "2px solid var(--green-500)"
                    : "1px solid var(--gray-200)",
                  position: "relative",
                }}
              >
                {isCurrent && (
                  <div
                    style={{
                      position: "absolute",
                      top: -12,
                      left: "50%",
                      transform: "translateX(-50%)",
                      background: "var(--green-500)",
                      color: "white",
                      padding: "2px 12px",
                      borderRadius: 12,
                      fontSize: "0.75rem",
                      fontWeight: 600,
                    }}
                  >
                    Current Plan
                  </div>
                )}
                <h2
                  style={{
                    margin: "0 0 0.5rem",
                    color: tierColors[plan.name] || "inherit",
                  }}
                >
                  {plan.name}
                </h2>
                <div
                  style={{
                    fontSize: "2.5rem",
                    fontWeight: 700,
                    marginBottom: "0.25rem",
                  }}
                >
                  {formatPrice(plan.price_cents)}
                </div>
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--gray-500)",
                    marginBottom: "1.5rem",
                  }}
                >
                  {plan.daily_limit.toLocaleString()} requests/day
                </div>
                <ul
                  style={{
                    listStyle: "none",
                    padding: 0,
                    margin: "0 0 1.5rem",
                  }}
                >
                  {plan.features.map((f, i) => (
                    <li
                      key={i}
                      style={{
                        padding: "0.4rem 0",
                        fontSize: "0.85rem",
                        borderBottom:
                          i < plan.features.length - 1
                            ? "1px solid var(--gray-100)"
                            : "none",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span style={{ color: "var(--green-500)", fontWeight: 700 }}>
                        +
                      </span>
                      {f}
                    </li>
                  ))}
                </ul>
                {canUpgrade ? (
                  <button
                    onClick={() => handleUpgrade(plan.name)}
                    disabled={upgrading === plan.name}
                    style={{
                      width: "100%",
                      padding: "0.75rem",
                      borderRadius: 8,
                      border: "none",
                      background:
                        tierKey === "enterprise"
                          ? "var(--blue-500, #3b82f6)"
                          : "var(--green-500, #22c55e)",
                      color: "white",
                      fontWeight: 600,
                      fontSize: "0.9rem",
                      cursor: upgrading ? "wait" : "pointer",
                      opacity: upgrading && upgrading !== plan.name ? 0.5 : 1,
                    }}
                  >
                    {upgrading === plan.name
                      ? "Redirecting..."
                      : tierKey === "enterprise"
                        ? "Contact Sales"
                        : `Upgrade to ${plan.name}`}
                  </button>
                ) : isCurrent ? (
                  <div
                    style={{
                      width: "100%",
                      padding: "0.75rem",
                      borderRadius: 8,
                      background: "var(--gray-100, #f3f4f6)",
                      color: "var(--gray-500)",
                      fontWeight: 600,
                      fontSize: "0.9rem",
                      textAlign: "center",
                    }}
                  >
                    Current Plan
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <div
        style={{
          textAlign: "center",
          marginTop: "2.5rem",
          padding: "1.5rem",
          background: "var(--surface-alt)",
          borderRadius: 12,
          fontSize: "0.9rem",
          color: "var(--gray-500)",
        }}
      >
        Need a custom plan or have questions? Reach out at{" "}
        <strong>hello@carbonmesh.dev</strong>
      </div>
    </div>
  );
}
