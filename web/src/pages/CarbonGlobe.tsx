import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Globe, { type GlobeInstance } from "globe.gl";
import * as THREE from "three";
import { api } from "../api/client";
import { useSnapshot, snapshotEnabled, qualityFromSource } from "../api/snapshot";
import { InfoTip } from "../components/InfoTip";

// A spinnable 3D globe plotting every cloud region at its real datacenter
// coordinates, glowing by carbon intensity (green = clean, red = dirty), with
// bar height = renewable share and a radar pulse per site. Data is the same
// real/estimated snapshot the dashboard uses — no continuous-surface coloring,
// so empty regions are simply dark (honest), not faked.

// Self-hosted from public/textures (copied from three-globe). Avoids three-globe's
// exports-field restriction on deep imports and any runtime CDN dependency.
const EARTH_NIGHT = "/textures/earth-night.jpg";
const EARTH_TOPOLOGY = "/textures/earth-topology.png";
const NIGHT_SKY = "/textures/night-sky.png";

interface GlobePoint {
  provider: string;
  region: string;
  location: string;
  grid_zone: string;
  lat: number;
  lng: number;
  intensity: number;
  renewable: number;
  source: string;
  quality?: "live" | "estimated" | "mock";
  gridLoadMw?: number | null;
}

// Total grid load (whole balancing authority, all consumers), formatted.
function formatLoad(mw?: number | null): string | null {
  if (mw == null) return null;
  return mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`;
}

function intensityRGB(v: number): [number, number, number] {
  if (v <= 50) return [34, 197, 94]; // green
  if (v <= 150) return [132, 204, 22]; // lime
  if (v <= 300) return [234, 179, 8]; // amber
  if (v <= 500) return [249, 115, 22]; // orange
  return [239, 68, 68]; // red
}

function intensityColor(v: number): string {
  const [r, g, b] = intensityRGB(v);
  return `rgb(${r},${g},${b})`;
}

// Renewable share: high % is greener, so the scale runs the opposite way from
// carbon intensity (high = green, low = red).
function renewableRGB(pct: number): [number, number, number] {
  if (pct >= 80) return [34, 197, 94]; // green
  if (pct >= 60) return [132, 204, 22]; // lime
  if (pct >= 40) return [234, 179, 8]; // amber
  if (pct >= 20) return [249, 115, 22]; // orange
  return [239, 68, 68]; // red
}

type Metric = "renewable" | "intensity";

function metricRGB(p: GlobePoint, metric: Metric): [number, number, number] {
  return metric === "renewable" ? renewableRGB(p.renewable) : intensityRGB(p.intensity);
}

// Altitude (in globe-radius units) of each beam for the selected metric.
function beamAltitude(p: GlobePoint, metric: Metric): number {
  const frac =
    metric === "intensity" ? Math.min(1, p.intensity / 800) : p.renewable / 100;
  return 0.04 + frac * 0.5;
}

// A tapered, open-ended beam of UNIT height whose color fades to transparent at
// the tip — it reads as a glowing light shaft, not a solid blocky cylinder. The
// height is applied per-frame via mesh.scale.y so the metric toggle just
// rescales existing meshes (no geometry rebuild).
function buildBeam(p: GlobePoint, globeRadius: number, colorMetric: Metric): THREE.Mesh {
  const radius = globeRadius * 0.0075;
  // Straight cylinder (no taper), unit height (scaled per-frame). Capped ends
  // (not open) so it reads as a filled volume: looking down from above, the
  // line of sight passes the transparent tip and lands on the full-color base
  // cap, so the beam appears filled with color rather than hollow.
  const geom = new THREE.CylinderGeometry(radius, radius, 1, 20, 8, false);
  geom.translate(0, 0.5, 0); // base at the origin (globe surface), tip near y=1

  const pos = geom.attributes.position;

  // Subtle, unique ripple on the tip so beams don't end in a perfect flat cut.
  // Build-time only (once per beam, never per frame): a gentle wave around the
  // rim with a per-beam random phase/amplitude shortens the top vertices, so
  // each beam fades out along its own uneven edge.
  const phase = Math.random() * Math.PI * 2;
  const lobes = 2 + Math.floor(Math.random() * 2); // 2–3 lobes
  const amp = 0.05 + Math.random() * 0.04;
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    if (y <= 0.78) continue; // only the top ~fifth ripples
    const k = (y - 0.78) / 0.22; // ramp in toward the tip
    const theta = Math.atan2(pos.getZ(i), pos.getX(i));
    const wave = Math.sin(theta * lobes + phase) * 0.5 + 0.5; // 0..1
    pos.setY(i, y - wave * amp * k);
  }

  const [r, g, b] = metricRGB(p, colorMetric).map((c) => c / 255) as [number, number, number];
  const colors = new Float32Array(pos.count * 4);
  for (let i = 0; i < pos.count; i++) {
    const t = Math.min(1, Math.max(0, pos.getY(i))); // 0 base → 1 tip (unit height)
    // Full, saturated color through the lower ~⅔ of the beam, fading to
    // transparent only near the tip — so the hue reads clearly even zoomed out.
    const alpha = Math.min(1, (1 - t) * 1.5);
    colors.set([r, g, b, alpha], i * 4);
  }
  geom.setAttribute("color", new THREE.BufferAttribute(colors, 4));

  // Normal (alpha) blending preserves the true hue. Additive blending washed
  // colors toward white — yellow especially — and over the bright city-lights
  // texture. depthWrite:false keeps overlapping beams compositing cleanly.
  const mat = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
    side: THREE.DoubleSide,
  });
  return new THREE.Mesh(geom, mat);
}

function useGlobePoints() {
  const { data: snapshot } = useSnapshot();
  const apiEnabled = !snapshotEnabled;

  const { data: apiRegions } = useQuery({
    queryKey: ["globe-regions"],
    queryFn: () => api.regions(),
    enabled: apiEnabled,
  });
  const { data: apiIntensities } = useQuery({
    queryKey: ["globe-intensities", apiRegions?.length ?? 0],
    queryFn: () =>
      api.carbonIntensityBatch(
        (apiRegions ?? []).map((r) => ({ provider: r.provider, region: r.region }))
      ),
    enabled: apiEnabled && !!apiRegions?.length,
  });

  return useMemo<GlobePoint[]>(() => {
    if (snapshot) {
      return snapshot.regions
        .map((r): GlobePoint | null => {
          const i = snapshot.intensities[`${r.provider}/${r.region}`];
          if (!i) return null;
          return {
            provider: r.provider,
            region: r.region,
            location: r.location,
            grid_zone: r.grid_zone,
            lat: r.latitude,
            lng: r.longitude,
            intensity: i.carbon_intensity_gco2_kwh,
            renewable: i.renewable_percentage,
            source: i.source,
            quality: i.quality ?? qualityFromSource(i.source),
            gridLoadMw: i.grid_load_mw,
          };
        })
        .filter((p): p is GlobePoint => p !== null);
    }
    if (apiRegions && apiIntensities) {
      return apiRegions
        .map((r): GlobePoint | null => {
          const i = apiIntensities[`${r.provider}/${r.region}`];
          if (!i) return null;
          return {
            provider: r.provider,
            region: r.region,
            location: r.location,
            grid_zone: r.grid_zone,
            lat: r.latitude,
            lng: r.longitude,
            intensity: i.carbon_intensity_gco2_kwh,
            renewable: i.renewable_percentage,
            source: i.source,
            quality: i.quality ?? qualityFromSource(i.source),
            gridLoadMw: i.grid_load_mw,
          };
        })
        .filter((p): p is GlobePoint => p !== null);
    }
    return [];
  }, [snapshot, apiRegions, apiIntensities]);
}

// Shared width so the metric toggles and the legend gradient always line up.
const PANEL_W = 234;

function MetricToggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Metric;
  onChange: (m: Metric) => void;
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: "0.64rem", color: "#94a3b8", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ display: "flex", width: PANEL_W, border: "1px solid rgba(255,255,255,0.2)", borderRadius: 999, overflow: "hidden", background: "rgba(10,15,20,0.6)" }}>
        {(["renewable", "intensity"] as Metric[]).map((m) => (
          <button
            key={m}
            onClick={() => onChange(m)}
            style={{
              flex: 1,
              textAlign: "center",
              whiteSpace: "nowrap",
              border: "none",
              cursor: "pointer",
              padding: "3px 6px",
              fontSize: "0.68rem",
              // Constant weight — the green fill signals "active", so we don't
              // bold (which would widen the text and wrap it to two lines).
              fontWeight: 500,
              background: value === m ? "var(--btn-green)" : "transparent",
              color: value === m ? "#fff" : "#cbd5e1",
            }}
          >
            {m === "renewable" ? "Renewable %" : "Carbon emissions"}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function CarbonGlobe() {
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const points = useGlobePoints();
  const [selected, setSelected] = useState<GlobePoint | null>(null);
  // Default to renewable % — the most intuitive read for a general audience
  // (higher = greener). Carbon emissions intensity (the more rigorous
  // "least damage" metric) is one toggle away.
  const [heightMetric, setHeightMetric] = useState<Metric>("renewable");
  const [colorMetric, setColorMetric] = useState<Metric>("renewable");

  // Read inside globe.gl accessors so a toggle takes effect without re-init.
  const heightMetricRef = useRef<Metric>(heightMetric);
  const colorMetricRef = useRef<Metric>(colorMetric);

  // Keep the refs current before the data effect below re-digests the globe.
  useEffect(() => {
    heightMetricRef.current = heightMetric;
    colorMetricRef.current = colorMetric;
  }, [heightMetric, colorMetric]);

  // Instantiate the globe once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const globe = new Globe(el);
    globe
      .globeImageUrl(EARTH_NIGHT)
      .bumpImageUrl(EARTH_TOPOLOGY)
      .backgroundImageUrl(NIGHT_SKY)
      .showAtmosphere(true)
      .atmosphereColor("#3a9efd")
      .atmosphereAltitude(0.18)
      // Points are invisible — they exist only as hover/click hit-targets that
      // span each beam. The visible beams are the custom layer below.
      .pointLat("lat")
      .pointLng("lng")
      .pointAltitude((d) => beamAltitude(d as GlobePoint, heightMetricRef.current))
      .pointRadius(0.5)
      .pointColor(() => "rgba(255,255,255,0)")
      .pointsMerge(false)
      .pointLabel((d) => {
        const p = d as GlobePoint;
        const tag =
          p.quality === "estimated"
            ? '<span style="color:#fbbf24">estimated · intermittent upstream</span>'
            : '<span style="color:#4ade80">live grid data</span>';
        return `
          <div style="font-family:system-ui;background:rgba(10,15,20,0.92);border:1px solid rgba(255,255,255,0.15);border-radius:8px;padding:8px 10px;color:#fff;font-size:12px;min-width:180px">
            <div style="font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#9ca3af;font-size:10px">${p.provider} · ${p.region}</div>
            <div style="margin:2px 0 6px;color:#d1d5db">${p.location} <span style="color:#6b7280">(${p.grid_zone})</span></div>
            <div style="font-size:18px;font-weight:700;color:${intensityColor(p.intensity)}">${p.intensity} <span style="font-size:11px;font-weight:400;color:#9ca3af">gCO2/kWh</span></div>
            <div style="color:#86efac">${p.renewable}% renewable</div>
            ${formatLoad(p.gridLoadMw) ? `<div style="color:#93c5fd">Grid load: ${formatLoad(p.gridLoadMw)} <span style="color:#6b7280">(whole grid)</span></div>` : ""}
            <div style="margin-top:4px;font-size:10px">${tag}</div>
          </div>`;
      })
      .ringLat("lat")
      .ringLng("lng")
      .ringMaxRadius((d) => 2 + ((d as GlobePoint).renewable / 100) * 3)
      .ringPropagationSpeed(1.4)
      .ringRepeatPeriod((d: object) => 2400 - ((d as GlobePoint).renewable / 100) * 1400)
      .ringColor((d: object) => {
        const [r, g, b] = metricRGB(d as GlobePoint, colorMetricRef.current);
        return (t: number) => `rgba(${r},${g},${b},${Math.sqrt(1 - t)})`;
      })
      .onPointClick((d: object) => {
        const p = d as GlobePoint;
        setSelected(p);
        globe.pointOfView({ lat: p.lat, lng: p.lng, altitude: 1.6 }, 900);
      })
      // Glowing light-shaft beams (replaces the blocky default cylinders).
      .customThreeObject((d: object) =>
        buildBeam(d as GlobePoint, globe.getGlobeRadius(), colorMetricRef.current),
      )
      .customThreeObjectUpdate((obj: object, d: object) => {
        const p = d as GlobePoint;
        const mesh = obj as THREE.Mesh;
        const c = globe.getCoords(p.lat, p.lng, 0); // base on the surface
        mesh.position.set(c.x, c.y, c.z);
        // Orient the beam (+Y) radially outward from the globe center.
        const radial = new THREE.Vector3(c.x, c.y, c.z).normalize();
        mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), radial);
        // Scale unit-height beam to the selected metric's altitude.
        mesh.scale.y = beamAltitude(p, heightMetricRef.current) * globe.getGlobeRadius();
        // Recolor in place (keeps the per-vertex alpha gradient) so the color
        // metric toggle updates without rebuilding geometry.
        const colorAttr = (mesh.geometry as THREE.BufferGeometry).getAttribute(
          "color",
        ) as THREE.BufferAttribute;
        const [cr, cg, cb] = metricRGB(p, colorMetricRef.current).map((c) => c / 255);
        for (let i = 0; i < colorAttr.count; i++) colorAttr.setXYZ(i, cr, cg, cb);
        colorAttr.needsUpdate = true;
      });

    globe.width(el.clientWidth).height(el.clientHeight);
    const controls = globe.controls() as {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableZoom: boolean;
    };
    controls.autoRotateSpeed = 0.55;
    controls.enableZoom = true;

    // Capture mode: `?lng=120` (optionally &lat=&alt=) freezes the camera at an
    // exact longitude, so screenshot frames have perfectly uniform rotation for
    // building a smooth GIF. With no params, the live app auto-rotates.
    const params = new URLSearchParams(window.location.search);
    const capLng = params.get("lng");
    if (capLng !== null) {
      controls.autoRotate = false;
      globe.pointOfView({
        lat: parseFloat(params.get("lat") ?? "12"),
        lng: parseFloat(capLng),
        altitude: parseFloat(params.get("alt") ?? "2.9"),
      });
    } else {
      controls.autoRotate = true;
      globe.pointOfView({ lat: 25, lng: 0, altitude: 2.4 });
    }

    globeRef.current = globe;

    const onResize = () => globe.width(el.clientWidth).height(el.clientHeight);
    window.addEventListener("resize", onResize);

    // Pause auto-rotation while the user is interacting; resume after.
    let resumeTimer: ReturnType<typeof setTimeout>;
    const pause = () => {
      controls.autoRotate = false;
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => {
        controls.autoRotate = true;
      }, 3500);
    };
    el.addEventListener("pointerdown", pause);

    return () => {
      window.removeEventListener("resize", onResize);
      el.removeEventListener("pointerdown", pause);
      clearTimeout(resumeTimer);
      globe._destructor?.();
      el.replaceChildren();
    };
  }, []);

  // Feed data into the globe whenever it changes.
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    // Fresh array copies force globe.gl to re-digest, so the accessors re-read
    // the metric refs: beams rescale (height) and recolor (color), rings and
    // hit-targets update too.
    globe
      .pointsData([...(points as object[])])
      .ringsData([...(points as object[])])
      .customLayerData([...(points as object[])]);
  }, [points, heightMetric, colorMetric]);

  const liveCount = points.filter((p) => p.quality === "live").length;
  const estCount = points.filter((p) => p.quality === "estimated").length;
  // `?bare` hides the overlays — used only for capturing clean globe screenshots.
  const bare =
    typeof window !== "undefined" && window.location.search.includes("bare");

  return (
    <div style={{ position: "relative", width: "100%", height: "calc(100vh - 56px)", background: "#000", overflow: "hidden" }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />

      {/* Title overlay */}
      <div style={{ position: "absolute", top: 20, left: 24, color: "#fff", pointerEvents: "none", textShadow: "0 1px 8px rgba(0,0,0,0.8)", display: bare ? "none" : undefined }}>
        {/* Visually hidden — kept for the document outline / screen readers. */}
        <h1
          style={{
            position: "absolute",
            width: 1,
            height: 1,
            padding: 0,
            margin: -1,
            overflow: "hidden",
            clip: "rect(0,0,0,0)",
            whiteSpace: "nowrap",
            border: 0,
          }}
        >
          Carbon Globe
        </h1>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#cbd5e1", maxWidth: 380 }}>
          {points.length} cloud regions by live grid carbon emissions and renewable
          share. Drag to spin, scroll to zoom, hover a node for detail.
        </p>
        {points.length > 0 && (
          <p style={{ margin: "6px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
            <span style={{ color: "#4ade80" }}>● {liveCount} live</span>
            {estCount > 0 && <span style={{ color: "#fbbf24", marginLeft: 10 }}>● {estCount} estimated</span>}
          </p>
        )}
      </div>

      {/* Controls + legend (bottom-left) */}
      <div style={{ position: "absolute", bottom: 24, left: 24, color: "#fff", fontSize: "0.7rem", textShadow: "0 1px 6px rgba(0,0,0,0.8)", display: bare ? "none" : undefined }}>
        <div style={{ marginBottom: 10 }}>
          <MetricToggle label="Height" value={heightMetric} onChange={setHeightMetric} />
          <MetricToggle label="Color" value={colorMetric} onChange={setColorMetric} />
        </div>
        {colorMetric === "intensity" ? (
          <>
            <div style={{ marginBottom: 4, color: "#cbd5e1", display: "inline-flex", alignItems: "center" }}>
              Carbon intensity (gCO2/kWh)
              <InfoTip
                label="carbon intensity"
                placement="top"
                text="gCO₂/kWh = grams of CO₂ per kilowatt-hour — the carbon emitted for each unit of electricity the grid produces. Lower is greener."
              />
            </div>
            <div style={{ width: PANEL_W, height: 10, borderRadius: 5, background: "linear-gradient(90deg,#22c55e,#84cc16,#eab308,#f97316,#ef4444)" }} />
            <div style={{ display: "flex", justifyContent: "space-between", width: PANEL_W, marginTop: 2, color: "#94a3b8" }}>
              <span>0 (greener)</span>
              <span>500+ (dirtier)</span>
            </div>
          </>
        ) : (
          <>
            <div style={{ marginBottom: 4, color: "#cbd5e1", display: "inline-flex", alignItems: "center" }}>
              Renewable share
              <InfoTip
                label="renewable share"
                placement="top"
                text="The share of the grid's electricity coming from renewable sources (wind, solar, hydro) right now. Higher is greener."
              />
            </div>
            <div style={{ width: PANEL_W, height: 10, borderRadius: 5, background: "linear-gradient(90deg,#ef4444,#f97316,#eab308,#84cc16,#22c55e)" }} />
            <div style={{ display: "flex", justifyContent: "space-between", width: PANEL_W, marginTop: 2, color: "#94a3b8" }}>
              <span>0% (dirtier)</span>
              <span>100% (greener)</span>
            </div>
          </>
        )}
      </div>

      {/* Empty / loading state */}
      {points.length === 0 && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", pointerEvents: "none" }}>
          Loading live grid data…
        </div>
      )}

      {/* Selected detail panel */}
      {selected && (
        <div style={{ position: "absolute", top: 20, right: 24, width: 260, background: "rgba(10,15,20,0.92)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, padding: "16px 18px", color: "#fff", backdropFilter: "blur(8px)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ textTransform: "uppercase", letterSpacing: "0.5px", color: "#9ca3af", fontSize: "0.7rem", fontWeight: 700 }}>
              {selected.provider} · {selected.region}
            </div>
            <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: "1rem", lineHeight: 1, padding: 0 }}>×</button>
          </div>
          <div style={{ margin: "4px 0 12px", color: "#d1d5db", fontSize: "0.85rem" }}>
            {selected.location} <span style={{ color: "#6b7280" }}>({selected.grid_zone})</span>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: intensityColor(selected.intensity) }}>
            {selected.intensity}
            <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "#9ca3af" }}> gCO2/kWh</span>
          </div>
          <div style={{ color: "#86efac", marginTop: 2 }}>{selected.renewable}% renewable</div>
          {formatLoad(selected.gridLoadMw) && (
            <div style={{ color: "#93c5fd", marginTop: 6, fontSize: "0.85rem" }}>
              Grid load: {formatLoad(selected.gridLoadMw)}
              <span style={{ color: "#6b7280" }}> · whole grid, all consumers</span>
            </div>
          )}
          <div style={{ marginTop: 12, fontSize: "0.72rem", color: selected.quality === "estimated" ? "#fbbf24" : "#4ade80" }}>
            {selected.quality === "estimated" ? "Estimated — upstream API intermittent" : "Live grid data"}
            <span style={{ color: "#6b7280" }}> · {selected.source}</span>
          </div>
        </div>
      )}
    </div>
  );
}
