import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { section as sectionFn } from "../styles";

const section = sectionFn(1000);

function formatPrice(cents: number): string {
  if (cents === 0) return "Free";
  return `$${(cents / 100).toFixed(0)}/mo`;
}

export function Plans() {
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

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem", textAlign: "center" }}>Plans & Pricing</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2.5rem", textAlign: "center" }}>
        Start free. Scale when you're ready.
      </p>

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
            const isCurrent = billing?.tier.toLowerCase() === plan.name.toLowerCase();
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
                    margin: 0,
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
