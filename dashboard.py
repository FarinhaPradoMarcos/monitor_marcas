"""Dashboard em HTML. Estatico (dashboard.html, gerado na coleta) ou ao vivo (servidor.py)."""
import json
from pathlib import Path

import analise

SAIDA = Path(__file__).with_name("dashboard.html")
CHARTJS = ('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.6.1/dist/chart.umd.min.js" '
           'integrity="sha384-Emf5ZVIUiarAdhkgtqK+5/Z5qIvM6QoVrS+qAVtfyZVuD5lIHrac0me485+Antp0" '
           'crossorigin="anonymous"></script>')

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor de marcas</title>
__CHARTJS__
<style>
  :root { --fundo:#f6f7f9; --card:#fff; --texto:#1d2330; --suave:#5b6474; --borda:#e2e5ea; --base:#16a34a; }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  body { margin:0; font:15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background:var(--fundo); color:var(--texto); }
  header { padding:20px 24px 8px; }
  h1 { margin:0 0 4px; font-size:22px; }
  .sub { color:var(--suave); margin:0; }
  .filtros { display:flex; gap:16px; flex-wrap:wrap; padding:8px 24px 16px; align-items:end; }
  .filtros label { display:flex; flex-direction:column; font-size:13px; color:var(--suave); gap:4px; }
  select { font:inherit; padding:6px 10px; border:1px solid var(--borda); border-radius:8px; background:#fff; }
  main { padding:0 24px 32px; display:grid; gap:16px; grid-template-columns:repeat(auto-fit, minmax(420px, 1fr)); }
  .kpis { grid-column:1/-1; display:grid; gap:12px; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); }
  .kpi, section { background:var(--card); border:1px solid var(--borda); border-radius:12px; padding:16px; }
  .kpi .rot { font-size:12px; color:var(--suave); text-transform:uppercase; letter-spacing:.04em; }
  .kpi .val { font-size:26px; font-weight:700; margin-top:4px; }
  .kpi .var { font-size:13px; color:var(--suave); }
  section h2 { font-size:16px; margin:0 0 8px; }
  section p.nota { color:var(--suave); font-size:12px; margin:8px 0 0; }
  .largo { grid-column:1/-1; }
  .grafico { position:relative; height:300px; }
  details { margin-top:8px; font-size:13px; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--borda); vertical-align:top; }
  th { color:var(--suave); font-weight:600; }
  td.n { text-align:right; font-variant-numeric:tabular-nums; }
  a { color:#1d4ed8; }
  .tag { display:inline-block; padding:1px 8px; border-radius:999px; font-size:12px; background:#eef2ff; }
  .neg { background:#fee2e2; } .pos { background:#dcfce7; }
  .alerta { padding:8px 10px; border-radius:8px; margin:6px 0; background:#fff7ed; border:1px solid #fed7aa; }
  .alerta.risco { background:#fef2f2; border-color:#fecaca; }
  :focus-visible { outline:3px solid #2563eb; outline-offset:2px; }
</style>
</head>
<body>
<header>
  <h1>Monitor de marcas</h1>
  <p class="sub" id="periodo"></p>
</header>

<div class="filtros" role="group" aria-label="Filtros">
  <label id="l-coleta" hidden>Coleta
    <select id="f-coleta"></select>
  </label>
  <label>Segmento
    <select id="f-segmento"></select>
  </label>
  <label>Fonte das menções
    <select id="f-fonte"></select>
  </label>
</div>

<main>
  <div class="kpis" id="kpis" aria-live="polite"></div>

  <section class="largo"><h2>Alertas da semana</h2><div id="alertas"></div></section>

  <section><h2>Menções na semana</h2>
    <div class="grafico"><canvas id="g-mencoes" role="img" aria-label="Menções por marca, semana atual e anterior"></canvas></div>
    <details><summary>Ver dados em tabela</summary><div id="t-mencoes"></div></details></section>

  <section><h2>Share of voice</h2>
    <div class="grafico"><canvas id="g-share" role="img" aria-label="Participação de cada marca no total de menções"></canvas></div>
    <details><summary>Ver dados em tabela</summary><div id="t-share"></div></details></section>

  <section><h2>Sentimento das menções</h2>
    <div class="grafico"><canvas id="g-sent" role="img" aria-label="Percentual de menções positivas, neutras e negativas por marca"></canvas></div>
    <p class="nota">Só menções com a marca no título. Classificação automática: boa para tendência, erra ironia e gíria.
      Marcas com menos de 15 menções aparecem como "amostra pequena" na tabela.</p>
    <details><summary>Ver dados em tabela</summary><div id="t-sent"></div></details></section>

  <section><h2>YouTube: views dos vídeos novos</h2>
    <div class="grafico"><canvas id="g-yt" role="img" aria-label="Views somadas dos vídeos novos por marca"></canvas></div>
    <details><summary>Ver dados em tabela</summary><div id="t-yt"></div></details></section>

  <section class="largo"><h2>Interesse de busca no Google (últimos 90 dias)</h2>
    <div class="grafico"><canvas id="g-trends" role="img" aria-label="Interesse de busca diário por marca, com a marca base valendo 100 em média"></canvas></div>
    <p class="nota" id="nota-trends"></p>
    <details><summary>Ver dados em tabela (média da semana)</summary><div id="t-trends"></div></details></section>

  <section><h2>Menções por grupo</h2>
    <div class="grafico"><canvas id="g-grupo" role="img" aria-label="Total de menções por grupo empresarial"></canvas></div>
    <details><summary>Ver dados em tabela</summary><div id="t-grupo"></div></details></section>

  <section><h2>Evolução semanal das menções</h2>
    <div class="grafico"><canvas id="g-hist" role="img" aria-label="Menções por semana e por marca"></canvas></div>
    <p class="nota">Fica mais útil a cada coleta semanal.</p>
    <details><summary>Ver dados em tabela</summary><div id="t-hist"></div></details></section>

  <section><h2>Buscas em alta</h2><div id="em-alta"></div></section>
  <section><h2>Vídeos mais vistos</h2><div id="top-videos"></div></section>
  <section class="largo"><h2>Destaques por marca</h2><div id="destaques"></div></section>
</main>

<script id="dados" type="application/json">__DADOS__</script>
<script>
// R: dados da semana. Vem embutido no arquivo (modo estatico) ou da API /api/semana (modo ao vivo).
let R = JSON.parse(document.getElementById('dados').textContent), BASE, MARCAS;
const AO_VIVO = R === null;
const ATUALIZAR_S = 60;
const PALETA = ['#2563eb','#dc2626','#9333ea','#ea580c','#0891b2','#ca8a04','#db2777','#4f46e5','#0d9488','#65a30d','#7c3aed','#be123c'];
const cor = m => m === BASE ? getComputedStyle(document.documentElement).getPropertyValue('--base').trim()
                            : PALETA[MARCAS.filter(x => x !== BASE).indexOf(m) % PALETA.length];
const fmt = n => n == null ? '-' : n >= 1e6 ? (n/1e6).toFixed(1)+' mi' : n >= 1e3 ? (n/1e3).toFixed(1)+' mil' : String(Math.round(n));
const pct = (a, p) => (a == null || p == null) ? '-' : p ? ((a-p)/p*100 >= 0 ? '+' : '') + Math.round((a-p)/p*100) + '%' : (a ? 'novo' : '-');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = (t, u) => /^https?:\/\//.test(u || '') ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t);


// filtros
const fSeg = document.getElementById('f-segmento'), fFonte = document.getElementById('f-fonte');
const fColeta = document.getElementById('f-coleta');
function opcoes(sel, lista, todos) {  // recria as opcoes mantendo a escolha atual, se ainda existir
  const atual = sel.value;
  sel.innerHTML = (todos ? `<option value="">${todos}</option>` : '') +
    lista.map(([v, r]) => `<option value="${esc(v)}">${esc(r)}</option>`).join('');
  if ([...sel.options].some(o => o.value === atual)) sel.value = atual;
}
function carregar(novo) {
  R = novo; BASE = R.marca_base; MARCAS = Object.keys(R.marcas);
  opcoes(fSeg, [...new Set(MARCAS.map(m => R.marcas[m].segmento))].sort().map(s => [s, s]), 'Todos');
  opcoes(fFonte, R.fontes.map(f => [f, f === 'noticias' ? 'Notícias' : f === 'youtube' ? 'YouTube' : f]), 'Todas');
  const quando = R.gerado_em.slice(0, 16).replace('T', ' ');
  document.getElementById('periodo').textContent = `Semana de ${R.inicio} a ${R.fim} · marca base: ${BASE} · ` +
    (AO_VIVO ? `última coleta ${quando} UTC · tela atualizada às ${new Date().toLocaleTimeString('pt-BR')}`
             : `gerado em ${quando} UTC`);
  if (AO_VIVO) opcoes(fColeta, R.coletas.map((d, i) => [i ? d : '', i ? d : `${d} (mais recente)`]));
  desenhar();
}

const graficos = {};
function grafico(id, cfg) {
  graficos[id]?.destroy();
  graficos[id] = new Chart(document.getElementById(id), cfg);
}
function tabela(id, cab, linhas) {
  document.getElementById(id).innerHTML = `<table><thead><tr>${cab.map(c => `<th scope="col">${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${linhas.map(l => `<tr>${l.map((c, i) => i === 0 ? `<th scope="row">${esc(c)}</th>` : `<td class="n">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
// funcao (e nao objeto compartilhado): o Chart.js altera o objeto de opcoes que recebe
const base = () => ({ responsive: true, maintainAspectRatio: false, animation: false,
                      plugins: { legend: { labels: { boxWidth: 12 } } } });

function men(m, campo) {
  const fs = fFonte.value ? [fFonte.value] : R.fontes;
  return fs.reduce((s, f) => s + (R.mencoes[m][f]?.[campo] || 0), 0);
}
// a semana anterior so e comparavel se foi coletada por inteiro em todas as fontes selecionadas
const comparavel = () => (fFonte.value ? [fFonte.value] : R.fontes).every(f => R.comparavel[f]);
const varMen = m => comparavel() ? pct(men(m, 'atual'), men(m, 'anterior')) : 'sem base';

function desenhar() {
  const ms = MARCAS.filter(m => !fSeg.value || R.marcas[m].segmento === fSeg.value);
  const ordem = [...ms].sort((a, b) => men(b, 'atual') - men(a, 'atual'));

  // KPIs da marca base (dentro do segmento filtrado, se ela estiver nele)
  const k = document.getElementById('kpis');
  if (ms.includes(BASE)) {
    const tot = ms.reduce((s, m) => s + men(m, 'atual'), 0) || 1;
    const s = R.sentimento[BASE], t = R.trends.semana[BASE], y = R.youtube.por_marca[BASE];
    const pos = 1 + ordem.indexOf(BASE);
    k.innerHTML = [
      ['Menções de ' + BASE, men(BASE, 'atual'), varMen(BASE) + ' vs semana anterior'],
      ['Share of voice', Math.round(men(BASE, 'atual') / tot * 100) + '%', `${pos}º de ${ms.length} marcas`],
      ['Sentimento médio', s.score_medio == null ? '-' : (s.score_medio >= 0 ? '+' : '') + s.score_medio.toFixed(2),
       s.amostra_pequena ? 'amostra pequena' : 'de -1 a +1'],
      ['Views no YouTube', fmt(y.views), `${y.videos} vídeos novos`],
      ['Busca no Google', t.atual == null ? '-' : Math.round(t.atual), pct(t.atual, t.anterior) + ' vs semana anterior'],
    ].map(([r, v, x]) => `<div class="kpi"><div class="rot">${esc(r)}</div><div class="val">${esc(v)}</div><div class="var">${esc(x)}</div></div>`).join('');
  } else {
    k.innerHTML = `<div class="kpi"><div class="rot">Segmento ${esc(fSeg.value)}</div><div class="val">${ms.reduce((s, m) => s + men(m, 'atual'), 0)}</div><div class="var">menções na semana (${esc(BASE)} não está neste segmento)</div></div>`;
  }

  // menções atual x anterior
  const dsMen = [{ label: 'Semana atual', data: ordem.map(m => men(m, 'atual')), backgroundColor: ordem.map(cor) }];
  if (comparavel()) dsMen.push({ label: 'Semana anterior', data: ordem.map(m => men(m, 'anterior')), backgroundColor: '#cbd5e1' });
  grafico('g-mencoes', { type: 'bar', options: base(), data: { labels: ordem, datasets: dsMen } });
  tabela('t-mencoes', ['Marca', 'Atual', 'Anterior', 'Variação', 'Marca no título'],
    ordem.map(m => [m, men(m, 'atual'), comparavel() ? men(m, 'anterior') : 'sem base', varMen(m), men(m, 'titulo')]));

  // share
  const tot = ordem.reduce((s, m) => s + men(m, 'atual'), 0) || 1;
  grafico('g-share', { type: 'doughnut', options: base(), data: { labels: ordem,
    datasets: [{ data: ordem.map(m => men(m, 'atual')), backgroundColor: ordem.map(cor) }] } });
  tabela('t-share', ['Marca', 'Share'], ordem.map(m => [m, Math.round(men(m, 'atual') / tot * 100) + '%']));

  // sentimento (100%)
  const comSent = ordem.filter(m => { const s = R.sentimento[m]; return s.positivo + s.neutro + s.negativo > 0; });
  const p100 = (m, c) => { const s = R.sentimento[m]; const t = s.positivo + s.neutro + s.negativo; return t ? Math.round(s[c] / t * 100) : 0; };
  grafico('g-sent', { type: 'bar', data: { labels: comSent, datasets: [
      { label: 'Positivo', data: comSent.map(m => p100(m, 'positivo')), backgroundColor: '#16a34a' },
      { label: 'Neutro', data: comSent.map(m => p100(m, 'neutro')), backgroundColor: '#94a3b8' },
      { label: 'Negativo', data: comSent.map(m => p100(m, 'negativo')), backgroundColor: '#dc2626' } ] },
    options: { ...base(), indexAxis: 'y', scales: { x: { stacked: true, max: 100, ticks: { callback: v => v + '%' } }, y: { stacked: true } } } });
  tabela('t-sent', ['Marca', 'Positivo', 'Neutro', 'Negativo', 'Score médio'], comSent.map(m => {
    const s = R.sentimento[m];
    return [m + (s.amostra_pequena ? ' (amostra pequena)' : ''), s.positivo, s.neutro, s.negativo,
            s.score_medio == null ? '-' : s.score_medio.toFixed(2)]; }));

  // youtube
  const yOrd = [...ms].sort((a, b) => R.youtube.por_marca[b].views - R.youtube.por_marca[a].views);
  grafico('g-yt', { type: 'bar', data: { labels: yOrd, datasets: [{ label: 'Views', data: yOrd.map(m => R.youtube.por_marca[m].views), backgroundColor: yOrd.map(cor) }] },
    options: { ...base(), plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => fmt(v) } } } } });
  tabela('t-yt', ['Marca', 'Vídeos novos', 'Views', 'Views ganhas'], yOrd.map(m => {
    const y = R.youtube.por_marca[m]; return [m, y.videos, fmt(y.views), R.youtube.tem_historico ? fmt(y.views_ganhas) : 'sem histórico']; }));

  // trends
  grafico('g-trends', { type: 'line', data: { labels: R.trends.datas, datasets: ms.map(m => ({
      label: m, data: R.trends.series[m], borderColor: cor(m), backgroundColor: cor(m),
      borderWidth: m === BASE ? 3 : 1.5, pointRadius: 0, tension: .25 })) },
    options: { ...base(), interaction: { mode: 'index', intersect: false }, scales: { x: { ticks: { maxTicksLimit: 10 } } } } });
  document.getElementById('nota-trends').textContent =
    `Escala relativa: 100 = interesse médio de ${BASE} nos 90 dias. Marcas sem tópico próprio no Trends usam palavra-chave e ficam subestimadas.`;
  tabela('t-trends', ['Marca', 'Média da semana', 'Semana anterior', 'Variação'], ms.map(m => {
    const t = R.trends.semana[m]; return [m, t.atual == null ? '-' : t.atual.toFixed(0), t.anterior == null ? '-' : t.anterior.toFixed(0), pct(t.atual, t.anterior)]; }));

  // grupos
  const grupos = {};
  ms.forEach(m => { const g = R.marcas[m].grupo.replace(/\s*\(.*\)$/, ''); grupos[g] = (grupos[g] || 0) + men(m, 'atual'); });
  const gOrd = Object.keys(grupos).sort((a, b) => grupos[b] - grupos[a]);
  grafico('g-grupo', { type: 'bar', data: { labels: gOrd, datasets: [{ label: 'Menções', data: gOrd.map(g => grupos[g]), backgroundColor: '#6366f1' }] },
    options: { ...base(), indexAxis: 'y', plugins: { legend: { display: false } } } });
  tabela('t-grupo', ['Grupo', 'Menções'], gOrd.map(g => [g, grupos[g]]));

  // historico
  grafico('g-hist', { type: 'line', data: { labels: R.historico.semanas, datasets: ms.map(m => ({
      label: m, data: R.historico.series[m], borderColor: cor(m), backgroundColor: cor(m), borderWidth: m === BASE ? 3 : 1.5 })) },
    options: base() });
  tabela('t-hist', ['Marca', ...R.historico.semanas], ms.map(m => [m, ...R.historico.series[m]]));

  // listas
  const al = R.alertas.filter(a => ms.includes(a.marca));
  document.getElementById('alertas').innerHTML = al.length ? al.map(a => a.tipo === 'pico'
      ? `<div class="alerta">📈 <strong>${esc(a.marca)}</strong> em ${esc(a.fonte)}: ${a.de} → ${a.para} menções</div>`
      : `<div class="alerta risco">⚠️ <strong>${esc(a.marca)}</strong> · risco (sentimento ${a.score.toFixed(2)}): ${link(a.titulo, a.url)} <span class="sub">${esc(a.veiculo)}, ${esc(String(a.publicado_em).slice(0,10))}</span></div>`).join('')
    : '<p class="sub">Nenhum alerta nesta semana.</p>';

  document.getElementById('em-alta').innerHTML = R.trends.em_alta.length
    ? `<p class="sub">Buscas que mais cresceram ligadas a ${esc(BASE)}:</p><ul>${R.trends.em_alta.map(q => `<li>${esc(q.termo)} <span class="tag">${esc(q.valor)}</span></li>`).join('')}</ul>`
    : '<p class="sub">Sem dados.</p>';

  const top = R.youtube.top.filter(v => ms.includes(v.marca)).sort((a, b) => b.views - a.views).slice(0, 8);
  document.getElementById('top-videos').innerHTML = top.length ? `<table><thead><tr><th scope="col">Vídeo</th><th scope="col">Marca</th><th scope="col">Views</th></tr></thead><tbody>${
    top.map(v => `<tr><td>${link(v.titulo, v.url)}<br><span class="sub">${esc(v.canal)}</span></td><td>${esc(v.marca)}</td><td class="n">${fmt(v.views)}</td></tr>`).join('')}</tbody></table>` : '<p class="sub">Nenhum vídeo.</p>';

  document.getElementById('destaques').innerHTML = ordem.map(m => {
    const d = R.destaques[m]; const itens = [...d.negativas.map(x => ['neg', x]), ...d.positivas.map(x => ['pos', x])];
    if (!itens.length) return '';
    return `<h3 style="font-size:14px;margin:12px 0 4px">${esc(m)}</h3><ul>${itens.map(([c, x]) =>
      `<li><span class="tag ${c}">${c === 'neg' ? 'negativa' : 'positiva'}</span> ${link(x.titulo, x.url)} <span class="sub">${esc(x.veiculo)}</span></li>`).join('')}</ul>`;
  }).join('') || '<p class="sub">Sem destaques.</p>';
}

fSeg.addEventListener('change', desenhar);
fFonte.addEventListener('change', desenhar);

async function buscar() {
  try {
    const q = fColeta.value ? `?ate=${encodeURIComponent(fColeta.value)}` : '';
    const r = await fetch('/api/semana' + q, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    carregar(await r.json());
    document.getElementById('erro-api')?.remove();
  } catch (e) {
    if (!document.getElementById('erro-api')) document.querySelector('main').insertAdjacentHTML('afterbegin',
      `<section class="largo" id="erro-api" role="alert"><strong>Não consegui buscar os dados do servidor</strong> (${esc(e.message)}). Tentando de novo em ${ATUALIZAR_S}s.</section>`);
  }
}

if (window.Chart && AO_VIVO) {
  document.getElementById('l-coleta').hidden = false;
  fColeta.addEventListener('change', buscar);
  buscar();
  // so atualiza sozinho olhando a coleta mais recente (semana antiga nao muda)
  setInterval(() => { if (!fColeta.value && !document.hidden) buscar(); }, ATUALIZAR_S * 1000);
} else if (window.Chart) carregar(R);
else document.querySelector('main').insertAdjacentHTML('afterbegin',
  '<section class="largo"><strong>Não consegui carregar a biblioteca de gráficos.</strong> Verifique a conexão com a internet.</section>');
</script>
</body>
</html>
"""


def pagina_ao_vivo() -> str:
    """Mesma pagina, sem dados embutidos: o JavaScript busca em /api/semana e atualiza sozinho."""
    return PAGINA.replace("__CHARTJS__", CHARTJS).replace("__DADOS__", "null")


def gerar(con, config) -> Path:
    R = analise.semana(con, config)
    dados = json.dumps(R, ensure_ascii=False).replace("</", "<\\/")  # nao fechar o <script> antes da hora
    SAIDA.write_text(PAGINA.replace("__CHARTJS__", CHARTJS).replace("__DADOS__", dados), encoding="utf-8")
    return SAIDA


if __name__ == "__main__":
    import db
    cfg = json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8"))
    print(gerar(db.conectar(), cfg))
