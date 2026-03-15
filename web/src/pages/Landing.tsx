import { Link } from "react-router-dom";
import { section as sectionFn, card as baseCard, grid3, badge } from "../styles";

const section: React.CSSProperties = { ...sectionFn(), padding: "3rem 2rem" };
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };

export function Landing() {
  return (
    <div>
      {/* Hero */}
      <style>{`
        .hero-title { font-size: 3rem; }
        .hero-subtitle { font-size: 1.25rem; }
        .hero-section { padding: 5rem 2rem 4rem; }
        @media (max-width: 600px) {
          .hero-title { font-size: 1.75rem !important; }
          .hero-subtitle { font-size: 1rem !important; }
          .hero-section { padding: 3rem 1rem 2.5rem !important; }
          .hero-cta { flex-direction: column !important; align-items: stretch !important; }
          .hero-cta a { text-align: center; }
        }
      `}</style>
      <div
        className="hero-section"
        style={{
          background: "linear-gradient(135deg, var(--green-700), var(--green-900))",
          color: "white",
          padding: "5rem 2rem 4rem",
          textAlign: "center",
        }}
      >
        <h1
          className="hero-title"
          style={{ fontSize: "3rem", margin: "0 0 1rem", fontWeight: 700 }}
        >
          Zero-knowledge proofs.
          <br />
          Zero-carbon compute.
        </h1>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1.25rem",
            maxWidth: 700,
            margin: "0 auto 0.75rem",
            opacity: 0.9,
          }}
        >
          Carbon Mesh brokers ZK proof generation to the greenest GPU compute on
          Earth — hydro-powered data centers, geothermal facilities, and
          behind-the-meter renewables.
        </p>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1rem",
            maxWidth: 600,
            margin: "0 auto 2rem",
            opacity: 0.7,
          }}
        >
          Earn bounties from Boundless, Succinct, Scroll, Aleo, and more.
          We route your proofs. You keep the profit. The planet keeps the carbon.
        </p>
        <div
          className="hero-cta"
          style={{ display: "flex", gap: "1rem", justifyContent: "center" }}
        >
          <Link
            to="/broker"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              background: "var(--surface)",
              color: "var(--green-800)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Try the Broker
          </Link>
          <Link
            to="/dashboard"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              border: "2px solid rgba(255,255,255,0.4)",
              color: "white",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            View Live Grid Data
          </Link>
        </div>
      </div>

      <section style={section}>
        {/* The Play */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginBottom: "0.5rem",
          }}
        >
          Proof of Work 2.0 — Without the Guilt
        </h2>
        <p
          style={{
            textAlign: "center",
            color: "var(--gray-500)",
            marginBottom: "2rem",
          }}
        >
          ZK-Rollups need massive GPU power to generate proofs.
          The industry is decentralizing. You can earn by providing that compute.
        </p>

        <div style={card}>
          <div
            style={{
              fontFamily: "var(--mono)",
              fontSize: "0.9rem",
              background: "var(--surface-alt)",
              padding: "1.5rem",
              borderRadius: 8,
              lineHeight: 1.8,
            }}
          >
            <div style={{ color: "var(--gray-400)" }}>
              Traditional prover: Rent AWS GPU &rarr; Run 24/7 &rarr; Hope grid
              is clean &rarr; Collect bounty
            </div>
            <div style={{ color: "var(--green-700)", fontWeight: 600 }}>
              Carbon Mesh: &nbsp;Job posted &rarr; Find greenest GPU NOW &rarr;
              Spin up &rarr; Prove &rarr; Collect bounty &rarr; Shut down
            </div>
          </div>
        </div>

        <div style={grid3}>
          {[
            {
              title: "Green Gatekeeper",
              desc: "Hardcoded carbon policy: only dispatch to compute that meets your threshold. Zero-carbon mode available — behind-the-meter hydro, geothermal, wind.",
            },
            {
              title: "8 Prover Networks",
              desc: "Connected to Boundless, Succinct, Gevulot, Aleo, Scroll, zkSync, StarkNet, and Taiko. One API to broker them all.",
            },
            {
              title: "12+ Compute Sources",
              desc: "AWS Spot, GCP Preemptible, plus green ASIC centers: IREN (BC hydro), TeraWulf (NY hydro), Hive Digital (Iceland geothermal), Bitdeer (Norway), CoreWeave, Lambda Labs, Vast.ai, Akash.",
            },
            {
              title: "Energy Arbitrage",
              desc: "No hardware to buy. Rent spot GPUs for 10 minutes, generate the proof, collect the bounty, shut down. Pure software margin.",
            },
            {
              title: "Real-Time Grid Data",
              desc: "11 government-verified carbon sources (EIA, ENTSO-E, AEMO). We know the exact gCO2/kWh of every compute option, every minute.",
            },
            {
              title: "Profit Optimization",
              desc: "Only accepts jobs where bounty > compute cost + your minimum margin. Automatic profitability gating — no losing trades.",
            },
          ].map((item) => (
            <div key={item.title} style={card}>
              <span style={badge}>{item.title}</span>
              <p style={{ marginTop: "0.75rem", fontSize: "0.95rem" }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {/* How It Works */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginTop: "3rem",
            marginBottom: "1rem",
          }}
        >
          How It Works
        </h2>
        <div style={card}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1.5rem",
              textAlign: "center",
            }}
          >
            {[
              {
                step: "1",
                title: "Jobs Appear",
                desc: "Prover networks (Scroll, Boundless, etc.) post proof jobs with bounties. Our broker polls continuously.",
              },
              {
                step: "2",
                title: "Green Routing",
                desc: "We query every GPU provider, fetch live carbon intensity, and filter by your carbon policy.",
              },
              {
                step: "3",
                title: "Profit Check",
                desc: "Only dispatch if bounty minus compute cost exceeds your minimum margin. No unprofitable jobs.",
              },
              {
                step: "4",
                title: "Prove & Earn",
                desc: "Spin up the GPU, generate the ZK proof, submit to the network, collect the bounty, shut down.",
              },
            ].map((s) => (
              <div key={s.step}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    background: "var(--green-600)",
                    color: "white",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: "1.1rem",
                    marginBottom: "0.5rem",
                  }}
                >
                  {s.step}
                </div>
                <h3 style={{ margin: "0.5rem 0 0.25rem", fontSize: "1rem" }}>
                  {s.title}
                </h3>
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--gray-500)",
                    margin: 0,
                  }}
                >
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Green Compute Providers */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginTop: "3rem",
            marginBottom: "1rem",
          }}
        >
          Green Compute Providers
        </h2>
        <div style={{ ...card, overflow: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.85rem",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Provider
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Location
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Energy Source
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Behind-the-Meter
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>GPUs</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["IREN (Iris Energy)", "British Columbia", "100% Hydro", "Yes", "RTX 4090, A100"],
                ["TeraWulf", "Upstate New York", "90%+ Hydro (Lake Mariner)", "Yes", "RTX 4090"],
                ["Hive Digital", "Iceland / Sweden", "Geothermal + Hydro", "Yes", "A100, RTX 4090"],
                ["Bitdeer", "Norway / Bhutan", "Hydro", "Yes", "A100"],
                ["CoreWeave", "US (multi-region)", "Grid (varies)", "No", "H100, A100"],
                ["Lambda Labs", "US (Texas, CA)", "Grid (varies)", "No", "A100"],
                ["AWS Spot", "Global (75+ regions)", "Grid (varies)", "No", "T4, A100"],
                ["GCP Preemptible", "Global (35+ regions)", "Grid (varies)", "No", "T4, A100, L4"],
              ].map(([name, loc, energy, btm, gpus]) => (
                <tr
                  key={name}
                  style={{ borderBottom: "1px solid var(--gray-100)" }}
                >
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{name}</td>
                  <td style={{ padding: "0.5rem" }}>{loc}</td>
                  <td style={{ padding: "0.5rem" }}>{energy}</td>
                  <td style={{ padding: "0.5rem" }}>
                    {btm === "Yes" ? (
                      <span
                        style={{
                          color: "var(--green-600)",
                          fontWeight: 600,
                        }}
                      >
                        Yes
                      </span>
                    ) : (
                      <span style={{ color: "var(--gray-400)" }}>No</span>
                    )}
                  </td>
                  <td style={{ padding: "0.5rem" }}>{gpus}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* CTA */}
        <div style={{ textAlign: "center", margin: "3rem 0 1rem" }}>
          <Link
            to="/broker"
            style={{
              display: "inline-block",
              padding: "0.85rem 2.5rem",
              borderRadius: 8,
              background: "var(--green-600)",
              color: "white",
              fontWeight: 600,
              fontSize: "1.1rem",
              textDecoration: "none",
            }}
          >
            Simulate Your First Green Proof
          </Link>
          <p
            style={{
              marginTop: "0.75rem",
              color: "var(--gray-400)",
              fontSize: "0.85rem",
            }}
          >
            Free demo — see which GPU the broker picks and why
          </p>
        </div>
      </section>
    </div>
  );
}
