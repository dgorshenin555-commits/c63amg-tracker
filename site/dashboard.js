(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const money = (value) =>
    finite(value)
      ? "$" +
        value.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : "—";
  const signed = (value) =>
    finite(value)
      ? (value < 0 ? "−" : value > 0 ? "+" : "") + money(Math.abs(value))
      : "—";
  const percent = (value) =>
    finite(value)
      ? value.toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "%"
      : "—";
  const decimal = (value) =>
    finite(value)
      ? value.toLocaleString("ru-RU", { maximumFractionDigits: 2 })
      : "—";
  const date = (ts, options = {}) =>
    finite(ts) && ts > 0
      ? new Date(ts * 1000).toLocaleString("ru-RU", {
          timeZone: "Europe/Moscow",
          day: "2-digit",
          month: "short",
          ...options,
        })
      : "—";
  const tone = (value) =>
    finite(value) && value < 0
      ? "negative"
      : finite(value) && value > 0
        ? "positive"
        : "";
  const icon = (name) =>
    `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const text = (id, value) => {
    $(id).textContent = value;
  };
  const reasons = {
    late_or_invalid: "Сигнал старше 7 минут или время некорректно",
    price_moved: "Цена изменилась",
    no_inventory: "Нет долей для продажи",
    risk_limit: "Лимит риска",
    price_filter: "Цена вне диапазона",
    no_depth: "Нет глубины рынка",
    bad_signal: "Некорректный сигнал",
    no_fill: "Нет исполнения",
    paper_buy: "Виртуальная покупка",
    paper_sell: "Виртуальная продажа",
  };
  const reason = (value) =>
    reasons[value] ||
    (String(value || "").startsWith("orderbook_error:")
      ? "Ошибка котировки"
      : value || "Причина не указана");
  let state = null;
  let filter = "all";
  let query = "";
  let visible = 6;
  let inFlight = false;
  let loadError = "";

  function validate(s) {
    if (
      !s ||
      typeof s !== "object" ||
      !["cash", "started", "end", "updated", "copied", "skipped"].every((key) =>
        finite(s[key]),
      ) ||
      s.end <= s.started ||
      !s.positions ||
      Array.isArray(s.positions) ||
      typeof s.positions !== "object" ||
      !Array.isArray(s.events)
    ) {
      throw new Error("Формат state.json не соответствует данным счёта");
    }
    if (
      Object.values(s.positions).some(
        (p) => !p || typeof p !== "object" || !finite(p.qty) || !finite(p.cost),
      )
    ) {
      throw new Error("В state.json некорректные данные позиций");
    }
    if (s.events.some((e) => !e || typeof e !== "object"))
      throw new Error("В state.json некорректный журнал событий");
    return s;
  }

  function portfolio(s) {
    const positions = Object.values(s.positions).filter((p) => p.qty > 1e-9);
    const estimated = positions.some(
      (p) => !finite(p.mark_value) || p.mark_source === "cost_fallback",
    );
    const open = positions.reduce(
      (sum, p) => sum + (finite(p.mark_value) ? p.mark_value : p.cost),
      0,
    );
    const cost = positions.reduce((sum, p) => sum + p.cost, 0);
    const equity = finite(s.equity) ? s.equity : s.cash + open;
    return {
      positions,
      estimated,
      open,
      cost,
      equity,
      pnl: finite(s.total_pnl) ? s.total_pnl : equity - 1000,
      unrealized: finite(s.unrealized) ? s.unrealized : open - cost,
    };
  }

  function renderMetrics(s, p) {
    const parts = money(p.equity).split(".");
    $("equity").innerHTML =
      `${escape(parts[0])}<span class="cents">.${escape(parts[1])}</span>`;
    text(
      "pnl-badge",
      `${signed(p.pnl)} (${p.pnl < 0 ? "−" : p.pnl > 0 ? "+" : ""}${(Math.abs(p.pnl) / 10).toFixed(2)}%)`,
    );
    $("pnl-badge").className =
      "badge" + (p.pnl < 0 ? " negative" : p.pnl === 0 ? " neutral" : "");
    text("unrealized", signed(p.unrealized));
    $("unrealized").className = "value " + tone(p.unrealized);
    text(
      "valuation-label",
      p.estimated || s.valuation_status === "partial"
        ? "Оценка неполная"
        : s.valuation_status === "quoted"
          ? "По котировкам"
          : "Снимок счёта",
    );
    const total = Math.max(s.cash, 0) + Math.max(p.open, 0);
    const cashShare = total ? (Math.max(s.cash, 0) / total) * 100 : 0;
    const openShare = total ? (Math.max(p.open, 0) / total) * 100 : 0;
    $("cash-segment").style.width = cashShare + "%";
    $("open-segment").style.width = openShare + "%";
    text("cash-share", percent(cashShare));
    text("open-share", percent(openShare));
    $("allocation-bar").setAttribute(
      "aria-label",
      `Свободно ${percent(cashShare)}, в позициях ${percent(openShare)}`,
    );
    text("cash", money(s.cash));
    text("position-count", String(p.positions.length).padStart(2, "0"));
    text("open-value", money(p.open));
    text("copied", String(s.copied).padStart(2, "0"));
    text("skipped", String(s.skipped));
    text("experiment-result", signed(p.pnl));
    text(
      "realized",
      signed(finite(s.realized_pnl) ? s.realized_pnl : s.realized),
    );
    text("detail-open", money(p.open));
    text("detail-cost", money(p.cost));
    text(
      "valuation-time",
      date(s.valuation_at, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }) + " МСК",
    );
    const errors = Array.isArray(s.valuation_errors) ? s.valuation_errors : [];
    const quality = p.estimated
      ? "Часть позиций оценена по себестоимости; цена продажи неизвестна."
      : s.valuation_status === "partial"
        ? "Неполная оценка: часть котировок или метаданных недоступна."
        : s.valuation_status === "quoted"
          ? "Котировки доступны на момент оценки. Показан сохранённый снимок."
          : "Качество котировок в снимке не указано.";
    text(
      "data-quality",
      quality + (errors.length ? ` Ошибок оценки: ${errors.length}.` : ""),
    );
  }

  function renderChart(s) {
    const duration = (s.end - s.started) / 7;
    const days = Array.from({ length: 7 }, (_, i) => ({
      start: s.started + duration * i,
      copied: 0,
      skipped: 0,
    }));
    for (const event of s.events) {
      const ts = finite(event.ts) ? event.ts : event.detected;
      if (!finite(ts)) continue;
      const index = Math.floor((ts - s.started) / duration);
      if (index < 0 || index >= 7) continue;
      if (event.decision === "COPIED") days[index].copied++;
      if (event.decision === "SKIPPED") days[index].skipped++;
    }
    const max = Math.max(1, ...days.map((d) => d.copied + d.skipped));
    const total = days.reduce((sum, d) => sum + d.copied + d.skipped, 0);
    text("chart-total", String(total));
    $("activity-chart").innerHTML = days
      .map((d, i) => {
        const count = d.copied + d.skipped;
        const label = `День ${i + 1}, ${date(d.start)}: ${d.copied} скопировано, ${d.skipped} пропущено`;
        return `<div class="chart-column" tabindex="0" role="img" aria-label="${escape(label)}"><div class="chart-tooltip" aria-hidden="true">${escape(date(d.start))}<br>${d.copied} скопировано · ${d.skipped} пропущено</div><div class="bar-area"><div class="bar" style="height:${(count / max) * 100}%"><span class="skipped" style="height:${count ? (d.skipped / count) * 100 : 0}%"></span><span class="copied" style="height:${count ? (d.copied / count) * 100 : 0}%"></span></div></div><span class="chart-date">${escape(date(d.start, { month: "numeric" }))}</span></div>`;
      })
      .join("");
    const retained = s.events.length;
    const reported = s.copied + s.skipped;
    text(
      "chart-note",
      `По сохранённому журналу: ${retained} ${retained === reported ? "из" : "событий; всего счётчик:"} ${reported}. История стоимости не сохраняется.`,
    );
  }

  function positionMarkup(p, more = false) {
    const mark = finite(p.mark_value) ? p.mark_value : p.cost;
    const pnl = mark - p.cost;
    const quality =
      !finite(p.mark_value) || p.mark_source === "cost_fallback"
        ? "По себестоимости · нет котировки"
        : p.mark_source === "gamma_indicative"
          ? "Индикативная оценка"
          : p.mark_source === "best_bid"
            ? "По лучшей цене продажи"
            : "Оценка из снимка";
    const markName = /UFC|MMA/i.test(p.title || "")
      ? "UFC"
      : /ATP|WTA|tennis/i.test(p.title || "")
        ? "ATP"
        : "PM";
    return `<article class="${more ? "position-more" : "position-main"}"><div class="position-header"><span class="market-mark" aria-hidden="true">${markName}</span><span class="badge neutral">Виртуальная</span></div><h3 class="position-title">${escape(p.title || "Название рынка не указано")}</h3><div class="position-outcome">${escape(p.outcome || "Исход не указан")} · ${decimal(p.qty)} долей</div><div class="position-values"><dl><dt>Текущая оценка</dt><dd>${money(mark)}</dd></dl><dl><dt>Результат</dt><dd class="${tone(pnl)}">${signed(pnl)}</dd></dl></div><div class="position-meta"><span>Вложено ${money(p.cost)}</span><span>${escape(quality)}</span></div></article>`;
  }

  function renderPositions(p) {
    const wasOpen = Boolean($("more-positions")?.open);
    text("position-caption", `${p.positions.length} открыто`);
    if (!p.positions.length) {
      $("position-content").innerHTML =
        '<div class="empty"><strong>Нет открытых позиций</strong>Новые виртуальные покупки появятся здесь.</div>';
      return;
    }
    const positions = p.positions.slice().sort((a, b) => b.cost - a.cost);
    $("position-content").innerHTML =
      positionMarkup(positions[0]) +
      (positions.length > 1
        ? `<details class="positions-extra" id="more-positions" ${wasOpen ? "open" : ""}><summary>Ещё позиций: ${positions.length - 1}</summary>${positions
            .slice(1)
            .map((p) => positionMarkup(p, true))
            .join("")}</details>`
        : "");
  }

  function renderActivity(s) {
    const events = s.events
      .filter(
        (e) =>
          (filter === "all" || e.decision === filter) &&
          (!query ||
            `${e.market || ""} ${e.outcome || ""}`
              .toLocaleLowerCase("ru-RU")
              .includes(query)),
      )
      .slice()
      .sort(
        (a, b) =>
          (b.detected || b.ts || 0) - (a.detected || a.ts || 0) ||
          (b.ts || 0) - (a.ts || 0),
      );
    text("event-count", String(events.length));
    if (!events.length) {
      $("activity-list").innerHTML =
        `<div class="empty"><strong>${s.events.length ? "Ничего не найдено" : "Событий пока нет"}</strong>${s.events.length ? "Измените фильтр или поисковый запрос." : "Новые сигналы появятся после следующего опроса."}</div>`;
    } else {
      $("activity-list").innerHTML = events
        .slice(0, visible)
        .map((e) => {
          const copied = e.decision === "COPIED";
          const skipped = e.decision === "SKIPPED";
          const price = finite(e.price)
            ? (e.price * 100).toLocaleString("ru-RU", {
                maximumFractionDigits: 1,
              }) + "¢"
            : "—";
          const ts = finite(e.detected) ? e.detected : e.ts;
          const side =
            e.side === "BUY"
              ? "Покупка"
              : e.side === "SELL"
                ? "Продажа"
                : e.side || "Сторона не указана";
          const sim = finite(e.sim_price)
            ? ` · Наша цена ${(e.sim_price * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}¢`
            : "";
          return `<article class="trade"><span class="trade-icon ${copied ? "copied" : ""}">${icon(copied ? "check" : "skip")}</span><div class="trade-body"><div class="trade-title">${escape(e.market || "Название рынка не указано")}</div><div class="trade-sub">${escape(side)} · ${escape(e.outcome || "—")}${escape(sim)}</div></div><div class="trade-status ${copied ? "copied" : ""}"><strong>${copied ? "Скопировано" : skipped ? "Пропущено" : "Статус неизвестен"}</strong><span>${escape(reason(e.reason))}</span></div><div class="trade-price">${price}<div class="trade-time">${escape(date(ts, { hour: "2-digit", minute: "2-digit" }))}</div></div></article>`;
        })
        .join("");
    }
    $("load-more").hidden = events.length <= visible;
  }

  function renderSettlements(s) {
    const events = (Array.isArray(s.settlements) ? s.settlements : [])
      .slice()
      .reverse();
    text("settlement-count", "· " + events.length);
    $("settlement-list").innerHTML = events.length
      ? events
          .map(
            (e) =>
              `<article class="settlement"><div>${escape(e.market || "Название рынка не указано")}<div class="subtle">${escape(e.outcome)} · ${escape(e.result === "WIN" ? "Выигрыш" : e.result === "LOSS" ? "Проигрыш" : e.result === "SPLIT" ? "Расчёт 50/50" : e.result || "Расчёт")} · ${escape(date(e.resolved_at))}</div></div><span class="${tone(e.pnl)}">${signed(e.pnl)}</span></article>`,
          )
          .join("")
      : '<div class="empty"><strong>Расчётов пока нет</strong>Результаты появятся после официального разрешения рынков.</div>';
  }

  function renderProgress(s) {
    const now = Date.now() / 1000;
    const duration = s.end - s.started;
    const progress = Math.max(
      0,
      Math.min(100, ((now - s.started) / duration) * 100),
    );
    const finished = now >= s.end;
    const pending = now < s.started;
    const day = pending
      ? 0
      : Math.min(7, Math.floor((now - s.started) / (duration / 7)) + 1);
    text("experiment-day", String(day).padStart(2, "0"));
    text(
      "period-label",
      finished
        ? "Период завершён"
        : pending
          ? "До начала эксперимента"
          : "День эксперимента",
    );
    $("progress-percent").innerHTML = `${Math.round(progress)}<small>%</small>`;
    $("progress-ring").style.strokeDashoffset = String(
      213.63 * (1 - progress / 100),
    );
    $("progress-fill").style.width = progress + "%";
    $("progress").setAttribute("aria-valuenow", String(Math.round(progress)));
    text(
      "start-date",
      date(s.started, { hour: "2-digit", minute: "2-digit" }) + " МСК",
    );
    text(
      "end-date",
      date(s.end, { hour: "2-digit", minute: "2-digit" }) + " МСК",
    );
    const hours = Math.max(0, Math.ceil((s.end - now) / 3600));
    text(
      "period-caption",
      finished
        ? "Период завершён. Результаты — по последнему снимку."
        : pending
          ? "Эксперимент ещё не начался."
          : `До конца ${Math.floor(hours / 24)} дн. ${hours % 24} ч. · календарное время`,
    );
    text(
      "calendar-title",
      `${date(s.started)} — ${date(s.end, { year: "numeric" })}`,
    );
    $("calendar").innerHTML = Array.from({ length: 7 }, (_, i) => {
      const start = s.started + (duration / 7) * i;
      const end = start + duration / 7;
      const elapsed = now >= end;
      const current = now >= start && now < end;
      const label = `День ${i + 1}, ${date(start)}: ${elapsed ? "прошёл" : current ? "текущий" : "впереди"}`;
      return `<div class="day-cell ${elapsed ? "elapsed" : current ? "current" : ""}" aria-label="${escape(label)}"><div class="day-label">${escape(date(start, { month: "numeric" }))}</div><div class="day-box" ${current ? 'aria-current="date"' : ""}>${elapsed ? "✓" : String(i + 1).padStart(2, "0")}</div></div>`;
    }).join("");
  }

  function renderFreshness() {
    if (!state) return;
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - state.updated));
    const stale = seconds > 900;
    text(
      "connection-label",
      loadError
        ? "Ошибка обновления"
        : stale
          ? "Снимок устарел"
          : "Данные актуальны",
    );
    $("connection-dot").classList.toggle("stale", stale || Boolean(loadError));
    text(
      "sync-note",
      `Снимок: ${date(state.updated, { hour: "2-digit", minute: "2-digit", second: "2-digit" })} МСК · проверка каждые 10 секунд`,
    );
    text(
      "feed-status",
      loadError
        ? "Ошибка загрузки снимка"
        : stale
          ? "Данные устарели"
          : state.feed_status === "live"
            ? "Последний опрос успешен"
            : state.feed_status || "Не указан",
    );
    text(
      "freshness-note",
      loadError
        ? "Не удалось обновить state.json. Показан последний успешно загруженный снимок; автоматические попытки продолжаются."
        : stale
          ? `Источник не обновлялся ${seconds >= 86400 ? Math.floor(seconds / 86400) + " дн." : seconds >= 3600 ? Math.floor(seconds / 3600) + " ч." : Math.floor(seconds / 60) + " мин."} Показанные суммы относятся к сохранённому снимку, а не к текущим котировкам.`
          : "Панель проверяет state.json каждые 10 секунд. Это не гарантирует такую же частоту публикации сделок API.",
    );
  }

  function render(s) {
    const p = portfolio(s);
    renderMetrics(s, p);
    renderPositions(p);
    renderChart(s);
    renderActivity(s);
    renderSettlements(s);
    renderProgress(s);
    renderFreshness();
  }

  async function load() {
    if (inFlight) return;
    inFlight = true;
    $("refresh").disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9000);
    try {
      const url = new URL(document.body.dataset.stateUrl, location.href);
      url.searchParams.set("ts", String(Date.now()));
      const response = await fetch(url, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = validate(await response.json());
      loadError = "";
      state = next;
      render(state);
      $("error-banner").hidden = true;
    } catch (error) {
      loadError =
        error.name === "AbortError"
          ? "Сервер не ответил за 9 секунд"
          : error.message || "Ошибка загрузки";
      text(
        "error-banner",
        `Не удалось обновить данные: ${loadError}. ${state ? "Показан предыдущий снимок." : "Автоматически повторим попытку."}`,
      );
      $("error-banner").hidden = false;
      if (state) renderFreshness();
      else text("connection-label", "Нет данных");
    } finally {
      clearTimeout(timeout);
      $("refresh").disabled = false;
      inFlight = false;
    }
  }

  for (const button of document.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      filter = button.dataset.filter;
      visible = 6;
      for (const item of document.querySelectorAll("[data-filter]"))
        item.setAttribute("aria-pressed", String(item === button));
      if (state) renderActivity(state);
    });
  }
  $("search").addEventListener("input", (event) => {
    query = event.target.value.trim().toLocaleLowerCase("ru-RU");
    visible = 6;
    if (state) renderActivity(state);
  });
  $("load-more").addEventListener("click", () => {
    visible += 10;
    if (state) renderActivity(state);
  });
  $("refresh").addEventListener("click", load);

  const tabs = [...document.querySelectorAll("[role=tab]")];
  function selectTab(tab) {
    for (const item of tabs) {
      const selected = item === tab;
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
      $(item.getAttribute("aria-controls")).hidden = !selected;
    }
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const next =
        event.key === "Home"
          ? tabs[0]
          : event.key === "End"
            ? tabs[tabs.length - 1]
            : tabs[
                (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
                  tabs.length
              ];
      selectTab(next);
      next.focus();
    });
  });
  for (const link of document.querySelectorAll(".nav a,.rail-link")) {
    link.addEventListener("click", () => {
      for (const item of document.querySelectorAll(".nav a,.rail-link"))
        item.classList.toggle("active", item.hash === link.hash);
    });
  }
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) load();
  });
  load();
  setInterval(load, 10000);
  setInterval(() => {
    if (state) {
      renderFreshness();
      renderProgress(state);
    }
  }, 5000);
})();
