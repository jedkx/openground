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

  let channelMeta = {};   // { [channel_id]: {unit, min, max, description} }
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

  function setChannels(keys) {
    channels = Array.from(new Set((keys || []).filter((k) => typeof k === "string"))).sort();
    latestByChannel = Object.fromEntries(channels.map((c) => [c, null]));
    channels.forEach((c) => {
      const meta = channelMeta[c];
      unitsByChannel[c] = (meta && meta.unit) || "";
      labelByChannel[c] = (meta && meta.description) || titleCase(c);
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
      name: "Telemetry Channel",
      description: "Scalar telemetry channel — real-time WebSocket stream with REST history.",
      cssClass: "icon-telemetry",
    });

    openmct.types.addType("openground.mission", {
      name: "Mission Status",
      description: "Link state, sequence stats, and limit violations for a mission.",
      cssClass: "icon-info",
    });

    // Merge declared channels (metadata) with any live channels not yet declared.
    // This way the UI is populated even before the first packet arrives.
    const declaredKeys = Object.keys(channelMeta);
    const allChannelKeys = [
      ...declaredKeys,
      ...channels.filter((k) => !channelMeta[k]),
    ];

    function ref(key) {
      return { namespace: "openground", key };
    }

    function telemetryValueMeta(name, unit) {
      return [
        { key: "utc", name: "Time", format: "utc", hints: { domain: 1 } },
        { key: "value", name, format: "float", units: unit, hints: { range: 1 } },
      ];
    }

    // Group channels by unit to build one stacked plot per unit family.
    const unitGroups = {};
    allChannelKeys.forEach((k) => {
      const unit = (channelMeta[k] && channelMeta[k].unit) || "";
      if (!unitGroups[unit]) unitGroups[unit] = [];
      unitGroups[unit].push(k);
    });

    const objects = {};

    // One stacked plot per unit group, parented under overview.
    const overviewPlots = [];
    Object.entries(unitGroups).forEach(([unit, keys]) => {
      const plotKey = "plot-" + (unit || "misc").replace(/[^a-zA-Z0-9]/g, "_");
      const plotName = unit || "Other";
      objects[`openground:${plotKey}`] = {
        identifier: ref(plotKey),
        name: plotName,
        type: "telemetry.plot.stacked",
        location: "openground:overview",
        composition: keys.map(ref),
      };
      overviewPlots.push(ref(plotKey));
    });

    objects["openground:root"] = {
      identifier: ref("root"),
      name: "OpenGround",
      type: "folder",
      location: "ROOT",
      composition: [
        ref("overview"),
        ref("lad"),
        ref("table"),
        ref("channels"),
      ],
    };

    objects["openground:overview"] = {
      identifier: ref("overview"),
      name: "Overview",
      type: "folder",
      location: "openground:root",
      // Mission Status first, then one plot per unit group.
      composition: [ref("missionStatus"), ...overviewPlots],
    };

    objects["openground:missionStatus"] = {
      identifier: ref("missionStatus"),
      name: "Mission Status",
      type: "openground.mission",
      location: "openground:overview",
    };

    objects["openground:channels"] = {
      identifier: ref("channels"),
      name: "Channels",
      type: "folder",
      location: "openground:root",
      composition: allChannelKeys.map(ref),
    };

    objects["openground:table"] = {
      identifier: ref("table"),
      name: "Telemetry Table",
      type: "table",
      location: "openground:root",
      composition: allChannelKeys.map(ref),
      configuration: { filters: {}, globalFilters: [] },
    };

    objects["openground:lad"] = {
      identifier: ref("lad"),
      name: "Last Known Values",
      type: "LadTable",
      location: "openground:root",
      composition: allChannelKeys.map(ref),
      configuration: { filters: {}, globalFilters: [] },
    };

    allChannelKeys.forEach((key) => {
      const meta = channelMeta[key] || {};
      const label = meta.description || labelByChannel[key] || key;
      const unit = meta.unit || unitsByChannel[key] || "";
      objects[`openground:${key}`] = {
        identifier: ref(key),
        name: label,
        type: "openground.telemetry",
        location: "openground:channels",
        telemetry: { values: telemetryValueMeta(label, unit) },
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
          valueNode.textContent = `${Number(datum.value).toFixed(2)} ${u}`.trim();
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

          const c = packet.ccsds || {};
          const apidHex = c.apid != null ? `0x${Number(c.apid).toString(16).padStart(3, "0")}` : "—";
          const lossStr = c.loss_rate != null ? `${esc(c.loss_rate)}%` : "—";

          const violations = Array.isArray(packet.limit_violations) ? packet.limit_violations : [];
          const violationsBlock =
            violations.length === 0
              ? `<p style="${UI.ok}">All channels within limits.</p>`
              : `<ul style="${UI.critList}">${violations
                  .map((v) => {
                    const bound = v.max != null ? `max ${v.max}` : `min ${v.min}`;
                    return `<li>${esc(v.channel)}: ${esc(v.value)} (${bound})</li>`;
                  })
                  .join("")}</ul>`;

          elementRef.innerHTML = `
          <div style="${UI.wrap};color:#e8eef8;">
            <h2 style="margin:0 0 14px 0;font-size:16px;font-weight:600;letter-spacing:0.03em">Mission Status</h2>
            <div style="display:grid;gap:10px;">
              <div style="${UI.card}">
                <div style="${UI.label}">Mission</div>
                <div style="${UI.value}">${esc(packet.mission_id)}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Link state</div>
                <div style="${UI.valueLg}">${esc(packet.system_state) || "—"}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Sequence</div>
                <div style="${UI.value}">SEQ ${c.seq != null ? esc(c.seq) : "—"} · lost ${c.lost != null ? esc(c.lost) : "—"} · loss ${lossStr}</div>
              </div>
              <div style="${UI.card}">
                <div style="${UI.label}">Ingest mode</div>
                <div style="${UI.value}">${esc((packet.source || {}).ingest_mode) || "—"}</div>
              </div>
              ${c.apid != null ? `
              <div style="${UI.card}">
                <div style="${UI.label}">CCSDS</div>
                <div style="${UI.value}">APID ${apidHex} · ${c.size != null ? esc(c.size) + " B" : "—"}</div>
              </div>` : ""}
              <div style="${UI.card}">
                <div style="${UI.label}">Limit violations</div>
                ${violationsBlock}
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
      const metaRes = await fetch("/api/openmct/telemetry/metadata");
      const metaPayload = await metaRes.json();
      const declaredChannels = Array.isArray(metaPayload.channels) ? metaPayload.channels : [];
      declaredChannels.forEach((c) => {
        if (c && c.id) channelMeta[c.id] = c;
      });
    } catch (e) {
      console.warn("[OpenGround] Failed to load channel metadata", e);
    }

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
            name: "Realtime",
            timeSystem: "utc",
            clock: "local",
            clockOffsets: {
              start: -FIVE_MINUTES,
              end: THIRTY_SECONDS,
            },
            presets: [
              {
                label: "5 minutes",
                bounds: { start: -FIVE_MINUTES, end: THIRTY_SECONDS },
              },
              {
                label: "30 minutes",
                bounds: { start: -THIRTY_MINUTES, end: THIRTY_SECONDS },
              },
              {
                label: "1 hour",
                bounds: { start: -ONE_HOUR, end: THIRTY_SECONDS },
              },
            ],
          },
          {
            name: "Fixed",
            timeSystem: "utc",
            bounds: {
              start: Date.now() - THIRTY_MINUTES,
              end: Date.now(),
            },
            presets: [
              {
                label: "Last 1 hour",
                bounds: {
                  start: () => Date.now() - ONE_HOUR,
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
                label: "Last 24 hours",
                bounds: {
                  start: () => Date.now() - ONE_DAY,
                  end: () => Date.now(),
                },
              },
            ],
            records: 10,
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

    location.hash = "#/browse/openground:overview";
    openmct.start(document.getElementById("openmct"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
