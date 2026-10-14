(() => {
  'use strict';

  const model = window.ORBIT_MODEL || {};
  const clusters = Array.isArray(model.clusters) ? model.clusters : [];
  const topicNames = ['Specialty coffee', 'Wellness', 'Sustainability', 'Design', 'Travel', 'Food'];
  const topicValues = cluster => [Number(cluster.coffeeRate || 0) / 100, ...(cluster.interestShares || []).map(Number)].slice(0, 6);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderAudience() {
    if (!clusters.length) return;
    const section = document.getElementById('audience');
    const view = section?.querySelector('.audience-view');
    if (!view) return;
    const segmentCard = view.querySelector(':scope > .card');
    const segmentHead = segmentCard?.querySelector('.card-head');
    if (segmentHead) {
      const subtitle = segmentHead.querySelector('p');
      if (subtitle) subtitle.textContent = `K-means segments from ${Number(model.profiles || 0).toLocaleString()} synthetic profiles`;
      segmentCard.querySelectorAll('.segment-row').forEach(node => node.remove());
      clusters.forEach((cluster, index) => {
        const row = element('div', 'segment-row');
        const icon = element('span', 'seg-icon', String(index + 1).padStart(2, '0'));
        const info = element('div', 'seg-info');
        info.append(element('b', '', cluster.name));
        info.append(element('small', '', `${cluster.size} profiles · age ${Math.round(cluster.avgAge)} · ${cluster.topLocation} · ${cluster.topPlatform}`));
        const bar = element('div', 'bar');
        const fill = element('i');
        fill.style.width = `${Math.max(0, Math.min(100, Number(cluster.share) || 0))}%`;
        bar.append(fill);
        row.append(icon, info, bar, element('span', 'pct', `${cluster.share}%`));
        segmentCard.append(row);
      });
    }

    const oldColumn = [...view.children].find(node => node !== segmentCard);
    const makeupCard = oldColumn?.querySelector('.card');
    if (makeupCard) {
      makeupCard.classList.add('training-snapshot-card');
      const head = makeupCard.querySelector('.card-head');
      if (head) {
        const title = head.querySelector('h2');
        const subtitle = head.querySelector('p');
        if (title) title.textContent = 'Training data snapshot';
        if (subtitle) subtitle.textContent = 'Synthetic audience data used by the model';
        head.querySelector('select')?.remove();
        [...makeupCard.children].filter(node => node !== head).forEach(node => node.remove());
        const facts = element('div', 'training-snapshot');
        const metric = (label, value) => {
          const item = element('div', 'training-snapshot-item');
          item.append(element('small', '', label), element('b', '', value));
          facts.append(item);
        };
        metric('Profiles', Number(model.profiles || 0).toLocaleString());
        metric('Audience clusters', String(clusters.length));
        metric('Coffee interest label', '0 / 1');
        makeupCard.append(facts);
      }
    }

    if (makeupCard && oldColumn) {
      makeupCard.remove();
      oldColumn.replaceWith(makeupCard);
    }
    let card = document.getElementById('interestPredictionCard');
    if (!card) {
      card = element('div', 'card interest-prediction-card');
      card.id = 'interestPredictionCard';
      const head = element('div', 'card-head');
      const title = element('div');
      title.append(element('h2', '', 'Interest prediction'), element('p', '', 'Modeled topic interest for a selected synthetic cluster'));
      const select = element('select', 'select');
      select.id = 'interestClusterSelect';
      select.setAttribute('aria-label', 'Choose an audience cluster for interest predictions');
      clusters.forEach(cluster => {
        const option = element('option', '', `${cluster.name} · ${cluster.share}% of profiles`);
        option.value = String(cluster.id);
        select.append(option);
      });
      head.append(title, select);
      const rows = element('div', 'prediction-grid');
      rows.id = 'interestPredictionRows';
      card.append(head, rows, element('p', 'prediction-note', 'Percentages are observed topic-interest shares within the selected synthetic cluster. The logistic regression separately predicts specialty-coffee interest; neither is a real campaign forecast.'));
      view.after(card);
      select.addEventListener('change', renderInterestRows);
    }
    renderInterestRows();
  }

  function renderInterestRows() {
    const cluster = clusters.find(item => String(item.id) === document.getElementById('interestClusterSelect')?.value) || clusters[0];
    const rows = document.getElementById('interestPredictionRows');
    if (!cluster || !rows) return;
    rows.replaceChildren();
    topicNames.forEach((name, index) => {
      const value = Math.max(0, Math.min(100, Math.round((topicValues(cluster)[index] || 0) * 100)));
      const row = element('div', 'prediction-row');
      const track = element('span', 'prediction-track');
      const fill = element('i');
      fill.style.width = `${value}%`;
      track.append(fill);
      row.append(element('span', 'prediction-label', name), track, element('b', 'prediction-value', `${value}%`));
      rows.append(row);
    });
  }

  function initTwinGate() {
    const concept = document.getElementById('twinConcept');
    const result = document.getElementById('twinResult');
    const run = document.getElementById('simulateTwin');
    const approve = document.getElementById('approveTwin');
    const cluster = document.getElementById('twinCluster');
    const topic = document.getElementById('twinTopic');
    const profile = document.getElementById('twinProfile');
    if (!concept || !result || !run || !approve) return;
    let hasFreshResult = false;
    let validation = document.getElementById('twinValidation');
    if (!validation) {
      validation = element('p', '', 'Add a content concept, then simulate to see the modeled audience fit.');
      validation.id = 'twinValidation';
      run.insertAdjacentElement('afterend', validation);
    }
    const invalidate = message => {
      hasFreshResult = false;
      result.hidden = true;
      approve.disabled = true;
      document.getElementById('twinChart')?.replaceChildren();
      document.getElementById('twinScore')?.replaceChildren('--');
      validation.textContent = message;
    };
    invalidate('Add a content concept, then simulate to see the modeled audience fit.');
    concept.addEventListener('input', () => invalidate(concept.value.trim() ? 'Your concept changed. Simulate again to refresh the audience fit.' : 'Add a content concept, then simulate to see the modeled audience fit.'));
    run.addEventListener('click', event => {
      const text = concept.value.trim();
      if (!text) {
        event.preventDefault();
        event.stopImmediatePropagation();
        invalidate('Enter a content concept before running the simulation.');
        concept.focus();
        return;
      }
      validation.textContent = 'Calculating the selected cluster’s modeled topic interest…';
      window.setTimeout(() => {
        if (concept.value.trim() !== text) return;
        result.hidden = false;
        hasFreshResult = true;
        approve.disabled = false;
        validation.textContent = 'Simulation complete. Review the synthetic audience comparison before approving.';
      }, 0);
    }, true);
    const resetForSelection = () => {
      invalidate('Selection changed. Run the simulation again to refresh the audience fit.');
      if (profile && typeof window.showTwinProfile === 'function') window.showTwinProfile();
    };
    cluster?.addEventListener('change', event => {
      resetForSelection();
      event.stopImmediatePropagation();
    }, true);
    topic?.addEventListener('change', event => {
      resetForSelection();
      event.stopImmediatePropagation();
    }, true);
    approve.addEventListener('click', event => {
      if (!hasFreshResult || !concept.value.trim()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        invalidate('Run a fresh simulation with a content concept before approving.');
      }
    }, true);
    document.getElementById('useAgentCaption')?.addEventListener('click', () => {
      window.setTimeout(() => concept.dispatchEvent(new Event('input', { bubbles: true })), 0);
    });
  }

  function setThemeIcon() {
    const icon = document.getElementById('themeIcon');
    const toggle = document.getElementById('themeToggle');
    if (!icon || !toggle) return;
    const light = document.body.classList.contains('light-theme');
    icon.innerHTML = light
      ? '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 15.4A8.5 8.5 0 0 1 8.6 3.2 8.5 8.5 0 1 0 20.8 15.4Z"/></svg>'
      : '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>';
  }

  function refreshWorkspace() {
    try {
      window.renderModelLab?.();
      const holdout = model.logistic?.holdout;
      const notes = document.getElementById('modelNotes');
      if (holdout && notes) {
        const lift = Number(holdout.accuracy) - Number(holdout.baselineAccuracy);
        notes.textContent = `Held out ${holdout.n} profiles from training. Baseline ${holdout.baselineAccuracy}% · balanced accuracy ${holdout.balancedAccuracy}% · precision ${holdout.precision}% · recall ${holdout.recall}% · F1 ${holdout.f1}%. ${lift >= 0 ? `${lift.toFixed(1)} points above baseline. ` : ''}Synthetic training data only; this does not measure real campaign performance.`;
      }
    } catch (error) { console.error('Model lab render failed', error); }
    try { window.updateDashboard?.(); } catch (error) { console.error('Overview refresh failed', error); }
    try { window.renderNotifications?.(); } catch (error) { console.error('Notifications render failed', error); }
    try { window.updateLiveClock?.(); } catch (error) { /* The clock may not be exposed in older saved copies. */ }
  }

  renderAudience();
  initTwinGate();
  setThemeIcon();
  document.getElementById('themeToggle')?.addEventListener('click', event => {
    event.stopImmediatePropagation();
    const next = document.body.classList.contains('light-theme') ? 'dark' : 'light';
    window.applyTheme?.(next, true);
    setThemeIcon();
  }, true);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshWorkspace(); });
  window.addEventListener('storage', refreshWorkspace);
  window.setInterval(refreshWorkspace, 15000);
  window.setInterval(() => {
    const button = document.getElementById('generateImage');
    if (button && button.textContent.trim() !== 'Generating image…') window.refreshImageStatus?.();
  }, 15000);
  refreshWorkspace();
})();
