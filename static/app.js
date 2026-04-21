(function () {
  const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
  let channels = [];
  const unitsByChannel = {};
  const labelByChannel = {};

  const UI = {
    card: "padding:12px;border:1px solid rgba(255,255,255,0.1);border-radius:2px;background:rgba(8,12,18,0.85)",
    label: "font-size:10px;letter-spacing:0.07em;text-transform:uppercase;font-weight:600;color:rgba(200,210,222,0.65)",
    value: "margin-top:6px;font-size:15px;font-weight:500;color:#e8eef8;font-variant-numeric:tabular-nums",
    valueLg: "margin-top:6px;font-size:20px;font-weight:600;color:#e8eef8;font-variant-numeric:tabular-nums",
    muted: "color:rgba(200,210,222,0.5);font-size:13px",
    ok: "color:rgba(160,200,170,0.85);font-size:13px",
    warnList: "margin:6px 0 0 0;padding-left:18px;color:#e8a878",
    critList: "margin:6px 0 0 0;padding-left:18px;color:#e07070",
    wrap: "padding:16px;max-width:560px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif",
  };

  let latestByChannel = {};
  let latestFullPacket = null;
  const subscribers = new Map();
  const statusListeners = new Set();
  let socket = null;

  const THIRTY_SECONDS = 30 * 1000;
  const ONE_MINUTE = THIRTY_SECONDS * 2;
  const FIVE_MINUTES = ONE_MINUTE * 5;
  const FIFTEEN_MINUTES = FIVE_MINUTES * 3;
  const THIRTY_MINUTES = FIFTEEN_MINUTES * 2;
  const ONE_HOUR = THIRTY_MINUTES * 2;
  const TWO_HOURS = ONE_HOUR * 2;
  const ONE_DAY = ONE_HOUR * 24;

  function titleCase(key) {
    return String(key)
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (m) => m.toUpperCase());
  }

  function guessUnits(channel) {
    if (channel.includes("temp")) return "degC";
    if (channel.includes("battery") || channel.endsWith("_pct")) return "%";
    if (channel === "lat" || channel === "lon" || channel.endsWith("_deg")) return "deg";
    if (channel.includes("velocity") || channel.endsWith("_mps")) return "m/s";
    if (channel.includes("altitude") || channel.endsWith("_m")) return "m";
    if (channel.endsWith("_km")) return "km";
    return "";
  }

  function setChannels(keys) {
    channels = Array.from(new Set((keys || []).filter((k) => typeof k === "string"))).sort();
    latestByChannel = Object.fromEntries(channels.map((c) => [c, null]));
    channels.forEach((c) => {
      unitsByChannel[c] = guessUnits(c);
      labelByChannel[c] = titleCase(c);
    });
  }

  function ensureChannelSet(channel) {
    if (!subscribers.has(channel)) {
      subscribers.set(channel, new Set());
    }
    return subscribers.get(channel);
  }

  function notifyStatus() {
    statusListeners.forEach((fn) => {
      try {
        fn(latestFullPacket);
      } catch (e) {
        console.warn("[OpenGround] mission status listener failed", e);
      }
    });
  }

  function publish(packet) {
    latestFullPacket = packet;
    notifyStatus();

    channels.forEach((channel) => {
      const value = packet[channel];
      if (typeof value !== "number") {
        return;
      }

      const datum = {
        value,
        utc: packet.epoch_ms,
      };

      latestByChannel[channel] = datum;

      const set = subscribers.get(channel);
      if (!set) {
        return;
      }

      set.forEach((cb) => cb(datum));
    });
  }

  function connect() {
    socket = new WebSocket(wsUrl);

    socket.onopen = function () {
      console.info("[OpenGround] WebSocket connected");
    };

    socket.onclose = function () {
      console.warn("[OpenGround] WebSocket closed; reconnecting");
      setTimeout(connect, 1200);
    };

    socket.onmessage = function (event) {
      let packet;
      try {
        packet = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!packet || typeof packet.epoch_ms !== "number") {
        return;
      }
      publish(packet);
    };
  }

  connect();

  setInterval(function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send("ping");
    }
  }, 25000);

  function channelIds() {
    return channels.map((key) => ({ namespace: "openground", key }));
  }

  function installOpenGroundPlugins() {
    openmct.types.addType("openground.telemetry", {
      name: "OpenGround Telemetry",
      description: "Scalar telemetry channel (WebSocket stream, REST history)",
      cssClass: "icon-telemetry",
    });

    openmct.types.addType("openground.mission", {
      name: "OpenGround Mission Summary",
      description: "MET, simulation profile, flight phase, link state, CCSDS, flight rules, plausibility faults",
      cssClass: "icon-info",
    });

    const objects = {
      "openground:root": {
        identifier: { namespace: "openground", key: "root" },
        name: "OpenGround",
        type: "folder",
        location: "ROOT",
        composition: [
          { namespace: "openground", key: "flightDeck" },
          { namespace: "openground", key: "missionStatus" },
          { namespace: "openground", key: "missionTable" },
          { namespace: "openground", key: "missionLad" },
          { namespace: "openground", key: "channels" },
        ],
      },
      "openground:flightDeck": {
        identifier: { namespace: "openground", key: "flightDeck" },
        name: "Flight deck (quick picks)",
        type: "folder",
        location: "openground:root",
        composition: channelIds().slice(0, 6),
      },
      "openground:missionStatus": {
        identifier: { namespace: "openground", key: "missionStatus" },
        name: "Mission Summary",
        type: "openground.mission",
        location: "openground:root",
      },
      "openground:channels": {
        identifier: { namespace: "openground", key: "channels" },
        name: "Telemetry Channels",
        type: "folder",
        location: "openground:root",
        composition: channelIds(),
      },
      "openground:missionTable": {
        identifier: { namespace: "openground", key: "missionTable" },
        name: "Mission Telemetry Table",
        type: "table",
        location: "openground:root",
        composition: channelIds(),
        configuration: {
          filters: {},
          globalFilters: [],
        },
      },
      "openground:missionLad": {
        identifier: { namespace: "openground", key: "missionLad" },
        name: "Mission LAD Table",
        type: "LadTable",
        location: "openground:root",
        composition: channelIds(),
        configuration: {
          filters: {},
          globalFilters: [],
        },
      },
    };

    function telemetryValueMeta(name, units) {
      return [
        { key: "utc", name: "Time", format: "utc", hints: { domain: 1 } },
        { key: "value", name, format: "float", units, hints: { range: 1 } },
      ];
    }

    channels.forEach((key) => {
      objects[`openground:${key}`] = {
        identifier: { namespace: "openground", key },
        name: labelByChannel[key] || key,
        type: "openground.telemetry",
        location: "openground:channels",
        telemetry: {
          values: telemetryValueMeta(labelByChannel[key] || key, unitsByChannel[key] || ""),
        },
      };
    });

    openmct.objects.addProvider("openground", {
      get: function (identifier) {
        return Promise.resolve(objects[`${identifier.namespace}:${identifier.key}`]);
      },
    });

    openmct.objects.addRoot({ namespace: "openground", key: "root" });

    openmct.composition.addProvider({
      appliesTo: function (domainObject) {
        return domainObject.identifier.namespace === "openground" && Array.isArray(domainObject.composition);
      },
      load: function (domainObject) {
        return Promise.resolve(domainObject.composition);
      },
    });

    openmct.telemetry.addProvider({
      supportsSubscribe: function (domainObject) {
        return domainObject.identifier.namespace === "openground" && channels.includes(domainObject.identifier.key);
      },
      supportsRequest: function (domainObject) {
        return domainObject.identifier.namespace === "openground" && channels.includes(domainObject.identifier.key);
      },
      subscribe: function (domainObject, callback) {
        const channel = domainObject.identifier.key;
        const set = ensureChannelSet(channel);
        set.add(callback);
        return function unsubscribe() {
          set.delete(callback);
        };
      },
      request: async function (domainObject, options) {
        const channel = domainObject.identifier.key;
        if (!channels.includes(channel)) {
          return [];
        }
        const start = Number(options && options.start) || Date.now() - 30 * 60 * 1000;
        const end = Number(options && options.end) || Date.now();

        const response = await fetch(`/api/openmct/telemetry/history?start=${start}&end=${end}`);
        const payload = await response.json();
        const rows = Array.isArray(payload.data) ? payload.data : [];

        return rows
          .filter((p) => typeof p[channel] === "number")
          .map((p) => ({
            utc: p.epoch_ms,
            value: p[channel],
          }));
      },
    });

    openmct.objectViews.addProvider({
      key: "openground.channel.view",
      name: "Channel Monitor",
      canView: function (domainObject) {
        return domainObject.identifier.namespace === "openground" && channels.includes(domainObject.identifier.key);
      },
      view: function (domainObject) {
        let elementRef = null;
        let unsubscribe = null;

        function render(datum) {
          if (!elementRef) {
            return;
          }

          const valueNode = elementRef.querySelector("[data-k='value']");
          const timeNode = elementRef.querySelector("[data-k='time']");

          if (!datum) {
            valueNode.textContent = "—";
            timeNode.textContent = "—";
            return;
          }

          const channel = domainObject.identifier.key;
          const u = unitsByChannel[channel] || "";
          let decimals = 2;
          if (channel === "lat" || channel === "lon" || channel.endsWith("_deg")) {
            decimals = 6;
          } else if (channel.endsWith("_phase_index") || channel.includes("accel_proxy")) {
            decimals = 4;
          }
          valueNode.textContent = `${Number(datum.value).toFixed(decimals)} ${u}`.trim();
          timeNode.textContent = new Date(datum.utc).toISOString().slice(11, 19) + "Z";
        }

        return {
          show: function (element) {
            elementRef = element;
            const channel = domainObject.identifier.key;
            element.innerHTML = `
            <div style="${UI.wrap}">
              <h2 style="margin:0 0 14px 0;font-size:16px;font-weight:600;color:#e8eef8;letter-spacing:0.02em">${domainObject.name}</h2>
              <div style="display:grid;gap:10px;max-width:400px;">
                <div style="${UI.card}">
                  <div style="${UI.label}">Latest value</div>
                  <div data-k="value" style="${UI.valueLg}">—</div>
                </div>
                <div style="${UI.card}">
                  <div style="${UI.label}">Timestamp (UTC)</div>
                  <div data-k="time" style="${UI.value}">—</div>
                </div>
              </div>
            </div>
          `;

            render(latestByChannel[channel]);

            const set = ensureChannelSet(channel);
            const cb = (datum) => render(datum);
            set.add(cb);
            unsubscribe = () => set.delete(cb);
          },
          destroy: function () {
            if (unsubscribe) {
              unsubscribe();
              unsubscribe = null;
            }
            elementRef = null;
          },
        };
      },
      priority: function () {
        return 1000;
      },
    });

    openmct.objectViews.addProvider({
      key: "openground.mission.view",
      name: "Mission Summary",
      canView: function (domainObject) {
        return domainObject.type === "openground.mission";
      },
      view: function () {
        let elementRef = null;
        let off = null;

        function esc(s) {
          if (s == null) {
            return "";
          }
          return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
        }

        function render(packet) {
          if (!elementRef) {
            return;
          }
          if (!packet) {
            elementRef.innerHTML = `<div style="${UI.wrap}"><p style="${UI.muted}">Awaiting telemetry…</p></div>`;
            return;
          }
          const faults = Array.isArray(packet.faults) ? packet.faults : [];
          const faultBlock =
            faults.length === 0
              ? `<p style="${UI.ok}">No plausibility faults.</p>`
              : `<ul style="${UI.critList}">${faults.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`;
          const rules = Array.isArray(packet.flight_rules) ? packet.flight_rules : [];
          const sevColor = (sev) => {
            const u = String(sev || "").toUpperCase();
            if (u === "CRITICAL") return "#e07070";
            if (u === "WARNING") return "#d9a060";
            return "rgba(200,210,222,0.85)";
          };
          const rulesBlock =
            rules.length === 0
              ? `<p style="${UI.ok}">No flight-rule violations.</p>`
              : `<ul style="margin:6px 0 0 0;padding-left:18px;">${rules
                  .map(
                    (r) =>
                      `<li style="color:${sevColor(r.severity)}"><span style="font-weight:600">${esc(r.id)}</span> — ${esc(r.message)}</li>`
                  )
                  .join("")}</ul>`;
          const metStr =
            typeof packet.met_hhmmss === "string" ? esc(packet.met_hhmmss) : "—";
          const metMs = typeof packet.met_ms === "number" ? esc(packet.met_ms) : "—";
          const sim = packet.sim || {};
          const modeStr = sim.telemetry_mode != null ? esc(sim.telemetry_mode) : "sim";
          const simLine = [
            `mode ${modeStr}`,
            sim.profile != null ? `<span style="font-weight:600">${esc(sim.profile)}</span>` : "",
            sim.dt_s != null ? `dt ${esc(sim.dt_s)} s` : "",
            sim.thrust_n != null && sim.thrust_n !== "" ? `${esc(sim.thrust_n)} N` : "",
            sim.mass_kg != null && sim.mass_kg !== "" ? `${esc(sim.mass_kg)} kg` : "",
            sim.timeline_path != null && sim.timeline_path !== "" ? `timeline ${esc(sim.timeline_path)}` : "",
            sim.iss_api_url != null && sim.iss_api_url !== "" ? `ISS ${esc(sim.iss_api_url)}` : "",
            sim.note != null && sim.note !== "" ? esc(sim.note) : "",
          ]
            .filter(Boolean)
            .join(" · ");
          const missionEvent =
            typeof packet.mission_event === "string" && packet.mission_event.trim()
              ? esc(packet.mission_event.trim())
              : "—";
          const issVisBlock =
            typeof packet.iss_visibility === "string" && packet.iss_visibility.trim()
              ? `<div style="${UI.card}">
                <div style="${UI.label}">ISS visibility (API)</div>
                <div style="${UI.value}">${esc(packet.iss_visibility.trim())}</div>
              </div>`
              : "";
          const c = packet.ccsds || {};
          const apidHex =
            c.apid != null && c.apid !== ""
              ? `0x${Number(c.apid).toString(16).padStart(3, "0")}`
              : "—";
          const seqStr = c.seq != null ? esc(c.seq) : "—";
          const sizeStr = c.size != null ? esc(c.size) : "—";
          const lossStr = c.loss_rate != null ? esc(c.loss_rate) : "—";
          elementRef.innerHTML = `
          <div style="${UI.wrap};color:#e8eef8;">
            <h2 style="margin:0 0 14px 0;font-size:16px;font-weight:600;letter-spacing:0.03em">Mission Summary</h2>
            <div style="display:grid;gap:10px;">
              <div style="${UI.card}">
                <div style="${UI.label}">Mission elapsed time</div>
                <div style="${UI.valueLg}">T+ ${metStr}</div>
                <div style="${UI.muted};margin-top:4px">${metMs} ms since T0</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Event / caption</div>
                <div style="${UI.value}">${missionEvent}</div>
              </div>
              ${issVisBlock}
              <div style="${UI.card}">
                <div style="${UI.label}">Telemetry mode (OPENGROUND_TELEMETRY_MODE)</div>
                <div style="${UI.value}">${simLine || "—"}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Flight phase</div>
                <div style="${UI.valueLg}">${esc(packet.phase)}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Ground link state</div>
                <div style="${UI.valueLg}">${esc(packet.system_state)}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">CCSDS frame</div>
                <div style="${UI.value}">APID ${apidHex} · SEQ ${seqStr} · ${sizeStr} B · loss ${lossStr}%</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Flight rules</div>
                ${rulesBlock}
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Plausibility faults</div>
                ${faultBlock}
              </div>
            </div>
          </div>`;
        }

        return {
          show: function (element) {
            elementRef = element;
            const r = () => render(latestFullPacket);
            statusListeners.add(r);
            off = () => statusListeners.delete(r);
            r();
          },
          destroy: function () {
            if (off) {
              off();
              off = null;
            }
            elementRef = null;
          },
        };
      },
      priority: function () {
        return 900;
      },
    });
  }

  async function bootstrap() {
    try {
      const res = await fetch("/api/openmct/telemetry/schema");
      const payload = await res.json();
      const schemaChannels = Array.isArray(payload.channels) ? payload.channels : [];
      setChannels(schemaChannels);
    } catch (e) {
      console.warn("[OpenGround] Failed to load telemetry schema; using empty channel list", e);
      setChannels([]);
    }

    openmct.setAssetPath("/openmct");

    openmct.install(openmct.plugins.LocalStorage());
    openmct.install(openmct.plugins.UTCTimeSystem());
    openmct.install(openmct.plugins.Espresso());
    openmct.install(
      openmct.plugins.Conductor({
        menuOptions: [
          {
            name: "Fixed",
            timeSystem: "utc",
            bounds: {
              start: Date.now() - THIRTY_MINUTES,
              end: Date.now(),
            },
            presets: [
              {
                label: "Last 24 hours",
                bounds: {
                  start: () => Date.now() - ONE_DAY,
                  end: () => Date.now(),
                },
              },
              {
                label: "Last 2 hours",
                bounds: {
                  start: () => Date.now() - TWO_HOURS,
                  end: () => Date.now(),
                },
              },
              {
                label: "Last 1 hour",
                bounds: {
                  start: () => Date.now() - ONE_HOUR,
                  end: () => Date.now(),
                },
              },
            ],
            records: 10,
          },
          {
            name: "Realtime",
            timeSystem: "utc",
            clock: "local",
            clockOffsets: {
              start: -THIRTY_MINUTES,
              end: THIRTY_SECONDS,
            },
            presets: [
              {
                label: "1 hour",
                bounds: {
                  start: -ONE_HOUR,
                  end: THIRTY_SECONDS,
                },
              },
              {
                label: "30 minutes",
                bounds: {
                  start: -THIRTY_MINUTES,
                  end: THIRTY_SECONDS,
                },
              },
              {
                label: "5 minutes",
                bounds: {
                  start: -FIVE_MINUTES,
                  end: THIRTY_SECONDS,
                },
              },
            ],
          },
        ],
      })
    );
    openmct.install(openmct.plugins.LADTable());
    openmct.install(
      openmct.plugins.Filters([
        "table",
        "telemetry.plot.overlay",
        "telemetry.plot.stacked",
      ])
    );

    installOpenGroundPlugins();

    location.hash = "#/browse/openground:flightDeck";
    openmct.start(document.getElementById("openmct"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
