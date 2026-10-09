/* UI orchestration. Every score comes from Python; no browser WER implementation. */
'use strict';
(() => {
    const UI_BUILD = 'dashboard-1.6.2';
    const $ = id => document.getElementById(id);
    function showUiFailure(message) {
        let box = $('uiFailure');
        if (!box) { box = document.createElement('div'); box.id='uiFailure'; document.body.prepend(box); }
        box.className='ui-failure';
        box.textContent=message;
        // Also readable if a stale CSS file was loaded.
        Object.assign(box.style,{padding:'18px',margin:'12px',background:'#fff3e8',color:'#663817',border:'1px solid #e6aa7b',borderRadius:'10px'});
        const label=$('healthLabel'); if(label) label.textContent='Application needs repair';
    }
    let boot;
    try { boot=JSON.parse($('bootstrap').textContent); }
    catch (_) { showUiFailure('Application data is missing. Restart the application and reload this page.'); return; }
    const expectedIds = ["modelScorecards", "modelSummarySection", "chartsSection", "chartScopeLabel", "comparisonDetails", "audioCasesSection", "runResultsSection", "completionNotice", "completionTitle", "completionText", "openCompletedRun", "dismissCompletion", "progressDestination", "audioFile", "batchFiles", "bootstrap", "caseChart", "caseTitle", "cleaningHint", "clearFilters", "closeDetail", "consent", "consentLabel", "cropEnd", "cropFields", "cropStart", "crumb", "detailAudio", "detailContent", "detailDialog", "detailMeta", "detailModel", "detailScoreView", "detailSummary", "detailTitle", "elevenReady", "evalForm", "exportBtn", "formError", "groundTruth", "healthLabel", "humainReady", "jobProgress", "kBest", "kBestModel", "kCases", "kDuration", "kMatched", "kModels", "kTranscripts", "language", "manifestFile", "manifestTemplate", "modelChart", "modelsCard", "newSubtitle", "newTitle", "overviewError", "page-overview", "printBtn", "progressBar", "progressCount", "progressStage", "progressTitle", "provenanceNote", "referenceCard", "refreshOverview", "resultsBody", "reuseCache", "rowCount", "runButton", "runCaseCount", "runCasesBody", "runCount", "runExportBtn", "runMeta", "runRescoreBtn", "runTableFoot", "runTablePaging", "runsList", "sampleDuration", "savedRunError", "savedRunMeta", "savedRunTitle", "selectEleven", "selectHumain", "seriesCount", "seriesNote", "sourceCard", "stopJob", "suppliedCard", "suppliedLabel1", "suppliedLabel2", "suppliedMode", "suppliedText1", "suppliedText2", "tableFoot", "tablePaging", "tableSearch", "themeToggle", "toast", "uiFailure", "workspaceMode", "workspaceNote", "youtubeUrl", "audioFoot", "pairA", "pairB", "pairNote", "pairScope", "pairedValues", "referenceGuard", "referenceConfirmed", "reviewEditor", "reviewStatus", "markConfirmed", "markExcluded", "clearReview", "correctedReference", "correctedConfirmed", "saveReference", "exportJson", "exportCsv"];
    const missing=expectedIds.filter(id=>!$(id));
    const templateBuild=document.querySelector('[data-workspace-build]')?.dataset.workspaceBuild;
    if (missing.length || templateBuild!==UI_BUILD || (!boot.offline && boot.ui_version!==UI_BUILD)) {
        showUiFailure('Application files are from different updates. If this is a GitHub clone, run git pull --ff-only in the project folder, restart the application, and refresh the browser. Missing: '+(missing.join(', ') || 'matching build version')+'. Saved results have not been removed.');
        return;
    }
    window.addEventListener('unhandledrejection', e=>{
        console.error(e.reason);
        showUiFailure('The page could not finish an operation: '+(e.reason?.message||String(e.reason))+'. Reload after verifying the repair. Existing results are unchanged.');
    });
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const percent = v => v == null ? '—' : (v * 100).toFixed(2) + '%';
    const duration = v => `${Math.floor((v || 0) / 60)}:${String(Math.floor((v || 0) % 60)).padStart(2, '0')}`;
    const state = { follow: null, finished: null, completing: false, page: 'overview', selectedRun: null, savedJob: null, runSummary: null, runRequestId: 0, runTablePage: 0, runView: 'normalized', requestId: 0, detailRequestId: 0, tablePage: 0, lastQuery: '', activeJob: null, run: null, job: null, summary: null, jobs: [], view: boot.default_view || 'normalized', source: 'sample', sample: null,
        detail: null, detailTab: 'words', rescore: null, timer: null, detailPage: 0, typeFilter: 'all' };
    let toastTimer;
    function toast(message, error = false) { $('toast').textContent = message; $('toast').className = 'toast show' + (error ? ' error' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.remove('show'), 6000); }
    // UI workflow only: watch the job created in this browser tab, not old history.
    const terminalStates = new Set(['complete', 'partial', 'failed', 'cancelled', 'interrupted']);
    function persistFollow() {
        try {
            if (state.follow) sessionStorage.setItem('asr-follow-run', JSON.stringify(state.follow));
            else sessionStorage.removeItem('asr-follow-run');
        } catch (_) { /* Storage may be disabled; in-tab tracking still works. */ }
    }
    function disarmFollow() {
        if (state.follow) { state.follow.auto = false; persistFollow(); }
    }
    function jumpTo(id) {
        const target = $(id); if (!target) return;
        if (target.tagName === 'DETAILS') target.open = true;
        const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
        requestAnimationFrame(() => {
            if (id === 'chartsSection' && state.summary) renderCharts();
            target.scrollIntoView({block:'start', behavior:reduced ? 'auto' : 'smooth'});
            if (target.hasAttribute('tabindex')) target.focus({preventScroll:true});
        });
    }
    async function followSubmittedRun(job, view) {
        const id = job.run_id || job.job_id;
        if (!id) throw new Error('The server did not return a run ID. Check Saved runs before retrying.');
        state.follow = {id, view, auto:true}; state.finished = null; persistFollow();
        $('completionNotice').classList.add('hidden');
        clearScopeInputs(); state.view = view; showPage('overview');
        toast('Evaluation accepted. Its result will open when ready.');
        await selectRun('all');
        if (state.follow && !$('jobProgress').classList.contains('hidden')) jumpTo('jobProgress');
    }
    async function openCompletedResult() {
        const finished = state.finished; if (!finished) return;
        state.runView = finished.view;
        const opened = await openRun(finished.id);
        if (!opened || state.page !== 'run' || state.selectedRun !== finished.id) return;
        $('completionNotice').classList.add('hidden');
        const cases = getAudioCases(state.runSummary);
        if (cases.length === 1 && cases[0].has_result !== false) {
            await openDetail(cases[0].case_id, '', finished.id);
        } else jumpTo('runResultsSection');
    }
    async function checkFollowCompletion() {
        const follow = state.follow;
        if (!follow || state.completing || boot.offline) return;
        const job = state.jobs.find(j => (j.run_id || j.job_id) === follow.id);
        if (!job || !terminalStates.has(job.status)) return;
        state.completing = true;
        state.finished = {...follow, status:job.status, name:job.name || 'Evaluation'};
        state.follow = null; persistFollow(); // Consume once, before any async navigation.
        $('completionTitle').textContent = job.status === 'complete' ? 'Evaluation complete' : 'Evaluation finished · ' + job.status;
        $('completionText').textContent = (job.name || follow.id) + ' · saved results are ready to inspect.';
        $('completionNotice').classList.remove('hidden');
        try {
            // Do not interrupt a different form, another inspector or a hidden tab.
            if (follow.auto && state.page === 'overview' && !$('detailDialog').open && !document.hidden)
                await openCompletedResult();
            else toast('Evaluation finished. Use View results to open it.');
        } catch (e) { toast('Result saved; could not open it: ' + e.message, true); }
        finally { state.completing = false; }
    }
    async function api(path, options = {}) {
        const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), options.long ? 120000 : 20000);
        const headers = { 'X-CSRF-Token': boot.csrf || '', 'X-ASR-UI-Build': UI_BUILD, ...(options.headers || {}) };
        let body = options.body;
        if (body && !(body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(body);
        }
        try {
            const r = await fetch(path, { method: options.method || 'GET', headers, body, signal: controller.signal, cache: 'no-store' });
            const data = await r.json().catch(() => ({error: 'The server returned an unreadable response. Restart the updated application.'}));
            if (!r.ok)
                throw new Error((data.error || 'Request failed.') + ` (HTTP ${r.status})`);
            return data;
        }
        catch (e) {
            if (e.name === 'AbortError')
                throw new Error('The local request timed out. Check Saved runs before submitting again.');
            throw e;
        }
        finally {
            clearTimeout(timeout);
        }
    }
    function showPage(name) {
        if (boot.offline && name !== 'overview')
            return;
        document.querySelectorAll('.page').forEach(p => p.classList.toggle('hidden', p.id !== 'page-' + name));
        document.querySelectorAll('.nav').forEach(b => b.classList.toggle('active', b.dataset.page === (name === 'run' ? 'runs' : name)));
        state.page = name;
        $('crumb').textContent = ({ overview: 'Overview', new: 'New evaluation', runs: 'Saved runs', run: 'Run details' })[name];
        if (name === 'runs')
            loadJobs().catch(e => { $('runsList').innerHTML = '<div class="load-error">' + esc(e.message) + '</div>'; toast(e.message, true); });
        if (name === 'new' && !state.rescore)
            resetFormMode();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    const policyCatalog = boot.normalization || {};
    const viewLabel = view => view === 'raw' ? 'No cleaning' : 'Cleaning';
    function profile() {
        // Python supplies the fixed rules. Do not duplicate them in JavaScript.
        if (!policyCatalog.cleaning_profile) throw new Error('Reload the updated application.');
        return {...policyCatalog.cleaning_profile, language: $('language').value};
    }
    function setProfile(p) { $('language').value = p.language || 'mixed'; }
    function selectedScoreView() {
        return document.querySelector('input[name="cleaningMode"]:checked').value;
    }
    function setScoreMode(view) {
        document.querySelectorAll('input[name="cleaningMode"]').forEach(r => { r.checked = r.value === view; });
        $('cleaningHint').textContent = view === 'raw'
            ? 'Compare spelling as supplied. Only display characters and spacing are prepared.'
            : 'Apply the same spelling rules to both texts. Originals stay unchanged.';
    }
    document.querySelectorAll('input[name="cleaningMode"]').forEach(r => {
        r.addEventListener('change', () => setScoreMode(r.value));
    });
    function resetFormMode() { state.rescore = null; $('newTitle').innerHTML = 'New evaluation<span class="title-dot">.</span>'; $('newSubtitle').textContent = 'Choose the audio, confirm the reference, then compare your models.'; $('sourceCard').classList.remove('hidden'); $('referenceCard').classList.toggle('hidden', state.source === 'batch'); $('modelsCard').classList.remove('hidden'); $('consentLabel').classList.remove('hidden'); $('runButton').textContent = 'Run evaluation →'; if ($('suppliedMode')) setSuppliedMode(false); }
    function setSuppliedMode(enabled) {
        $('suppliedMode').checked = enabled;
        $('suppliedCard').classList.toggle('hidden', !enabled);
        $('modelsCard').classList.toggle('hidden', enabled);
        $('consentLabel').classList.toggle('hidden', enabled);
        $('runButton').textContent = enabled ? 'Score supplied transcripts →' : 'Run evaluation →';
    }
    function sourceTab(name) {
        const changed = name !== state.source;
        if (name !== 'sample') setSuppliedMode(false);
        state.source = name;
        document.querySelectorAll('[data-source]').forEach(b => b.classList.toggle('active', b.dataset.source === name));
        document.querySelectorAll('.source-content').forEach(c => c.classList.toggle('hidden', c.id !== 'source-' + name));
        $('referenceCard').classList.toggle('hidden', name === 'batch');
        $('cropFields').classList.toggle('hidden', name === 'batch');
        if (changed) {
            $('referenceConfirmed').checked = false;
            $('groundTruth').value = ''; $('caseTitle').value = '';
            $('referenceGuard').textContent = 'Audio source changed. Add the reference for this source; the sample transcript was not carried over.';
        }
        if (name === 'sample' && state.sample) {
            $('groundTruth').value = state.sample.case.ground_truth;
            $('caseTitle').value = state.sample.case.title;
            $('cropStart').value = 0; $('cropEnd').value = '';
            $('referenceConfirmed').checked = true;
            $('referenceGuard').textContent = 'Included reference loaded for the included full clip. Review it after changing the crop.';
        }
    }
    function clearScopeInputs() { $('tableSearch').value = ''; state.tablePage = 0; }
    function scopeFilters() {
        // The Overview NEVER follows a run selection from History.
        return {run: 'all', q: $('tableSearch').value.trim(), model: 'all', language: 'all', origin: 'all'};
    }
    function scopeQuery() { return new URLSearchParams({...scopeFilters(), view: state.view, pair_a:state.pair?.[0]||'', pair_b:state.pair?.[1]||''}).toString(); }
    state.pair = [];
    const dateLabel = value => {
        const d = new Date(value);
        return Number.isNaN(d.getTime()) ? (value || 'Date not recorded') : d.toLocaleString();
    };
    function updateRunOptions() {
        // History is a list, not a selector affecting the dashboard.
        $('runCount').textContent = state.jobs.length;
        $('runsList').innerHTML = state.jobs.map(j => `<article class="run-card"><div><h3>${esc(j.name || j.run_id)}</h3><p>${esc(dateLabel(j.created_at))} · ${j.completed ?? 0}/${j.total ?? 0} cases · ${esc(j.mode || 'live')} · ${esc(j.run_id.slice(-6))}</p></div><div><span class="badge ${esc(j.status)}">${esc(j.status)}</span><button class="secondary" data-open-run="${esc(j.run_id)}">Open ↗</button></div></article>`).join('') || '<div class="empty-state">No saved runs yet.</div>';
    }
    async function loadJobs() {
        state.jobs = boot.offline ? (boot.jobs || [boot.job]).filter(Boolean) : (await api('/api/jobs')).jobs;
        if (!Array.isArray(state.jobs)) throw new Error('Saved-runs response is invalid.');
        updateRunOptions();
    }
    let openingSample = false;
    async function openSampleResults() {
        // This is a local re-score of the bundled texts, never a provider request.
        if (boot.offline || openingSample) return;
        openingSample = true;
        const buttons = [...document.querySelectorAll('[data-open-sample]')];
        const labels = buttons.map(button => button.textContent);
        buttons.forEach(button => { button.disabled = true; button.textContent = 'Opening sample…'; });
        try {
            clearTimeout(searchTimer);
            state.requestId++; // Ignore a pending response for the previous overview scope.
            await loadJobs();
            let job = state.jobs.find(j => j.status === 'complete' && j.mode === 'imported'
                && j.run_id.startsWith('sample_') && j.name === 'At the doctor · supplied transcripts');
            if (job) {
                const saved = await api('/api/results/' + encodeURIComponent(job.run_id));
                if (!saved.summary?.case_count) job = null;
            }
            if (!job) {
                job = await api('/api/sample/score', {
                    method: 'POST', body: { score_view: state.view }, long: true
                });
                await loadJobs();
            }
            clearScopeInputs();
            showPage('overview');
            await selectRun('all');
            const first = state.summary?.audio_cases?.find(c => c.run_id === job.run_id);
            if (first) await openDetail(first.case_id, '', first.run_id);
            toast('Sample results from saved transcripts. No ASR API calls.');
        } catch (e) {
            toast(e.message, true);
        } finally {
            openingSample = false;
            buttons.forEach((button, index) => { button.disabled = false; button.textContent = labels[index]; });
        }
    }
    async function selectRun(id = 'all') {
        const requestId = ++state.requestId;
        state.run = boot.offline ? (boot.job?.run_id || 'all') : 'all';
        clearTimeout(state.timer);
        document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
        $('exportBtn').disabled = true;
        $('overviewError').classList.add('hidden');
        $('page-overview').setAttribute('aria-busy', 'true');
        const query = scopeQuery();
        try {
            let result;
            if (boot.offline) {
                result = {summary: boot.summaries[state.view], jobs: state.jobs};
                // Older single-run exports remain readable with the shared renderer.
                if (!boot.overview) {
                    result.summary = JSON.parse(JSON.stringify(result.summary));
                    result.summary.rows.forEach(r => Object.assign(r, {run_id: boot.job.run_id, provider_key: r.model,
                        case_uid: boot.job.run_id + '/' + r.case_id, clip_id: r.case_id, included: true}));
                    result.summary.chart_rows = result.summary.rows;
                    result.summary.case_failures?.forEach(r => {r.run_id = boot.job.run_id;});
                }
            } else result = await api('/api/overview?' + query);
            if (requestId !== state.requestId) return; // Ignore out-of-order network replies.
            if (!result || !Array.isArray(result.jobs) || !result.summary || !Array.isArray(result.summary.models)) throw new Error('Saved-results response has the wrong structure. Restart the repaired backend.');
            state.jobs = result.jobs;
            state.summary = result.summary;
            state.lastQuery = query;
            state.job = null; // Saved-run navigation has independent state.
            updateRunOptions();
            // Show cases first; a chart failure must never hide the saved evaluations.
            renderTable(); renderSummary(); renderProgress();
            try { renderCharts(); } catch (chartError) {
                console.error(chartError); $('modelChart').textContent='Chart unavailable. Audio results are still listed below.';
                $('caseChart').textContent='Chart unavailable.';
            }
            const active = state.summary.active_jobs || state.jobs.filter(j => ['queued','running'].includes(j.status));
            if (!boot.offline && active.length) state.timer = setTimeout(pollWorkspace, 1800);
            await checkFollowCompletion();
        } catch (e) {
            if (requestId === state.requestId) {
                $('runMeta').textContent = 'Could not refresh this scope. Previous results may be out of date.';
                $('overviewError').textContent = 'Could not load saved results: ' + e.message + ' Click Refresh to retry. Existing files were not removed.';
                $('overviewError').classList.remove('hidden');
                $('tableFoot').textContent = 'Results could not be refreshed. This is not an empty workspace.';
                if (state.follow && !boot.offline) state.timer = setTimeout(pollWorkspace, 3000);
                toast(e.message, true);
            }
        } finally {
            if (requestId === state.requestId) $('page-overview').setAttribute('aria-busy', 'false');
        }
    }
    async function pollWorkspace() {
        if (boot.offline) return;
        await selectRun(state.run);
    }
    function renderProgress() {
        if (boot.offline) { $('jobProgress').classList.add('hidden'); state.activeJob=null; return; }
        const active = state.summary.active_jobs || [];
        const j = active.find(j => (j.run_id || j.job_id) === state.follow?.id) || active.find(j => j.status === 'running') || active[0];
        state.activeJob = j?.job_id || j?.run_id || null;
        $('jobProgress').classList.toggle('hidden', !j);
        if (!j) return;
        $('progressTitle').textContent = j.name;
        $('progressStage').textContent = (j.current_case ? j.current_case + ' · ' : '') + (j.stage || '') + (active.length > 1 ? ` · ${active.length} active jobs` : '');
        $('progressDestination').textContent = state.follow?.auto ? 'When finished: this run opens automatically.' : 'Results are checkpointed. Other saved cases remain available below.';
        $('progressCount').textContent = `${j.completed} / ${j.total} cases`;
        $('progressBar').style.width = (100 * j.completed / Math.max(1, j.total)) + '%';
    }
    function renderSummary() {
        const s=state.summary, cases=getAudioCases(s), p=s.comparison||{};
        $('runMeta').textContent = boot.offline ? `Frozen report · ${dateLabel(boot.exported_at)}` : `${state.jobs.length} saved runs · all evaluations below`;
        $('kCases').textContent=cases.length;
        $('kDuration').textContent=`${s.run_count} runs · repeated attempts stay visible`;
        $('kTranscripts').textContent=s.successful_transcripts;
        $('kModels').textContent=`of ${s.recorded_model_attempts||s.rows.length} recorded model outputs · ${s.failures} failed`;
        $('kMatched').textContent=s.audio_input_count??s.case_count;
        $('audioFoot').textContent=`${duration(s.duration)} across evidenced inputs · ${s.media_unavailable_cases||0} without audio metadata`;
        $('kBest').textContent=p.matched??0;
        $('kBestModel').textContent=p.flagged ? `${p.flagged} require reference review` : 'Common successful cases for the pair below';
        $('provenanceNote').textContent=[s.audio_identity_note, s.comparison_note,
            `${s.earlier_attempts} earlier model attempts remain in history but are not counted again in aggregates.`,
            `Successful-output provenance: ${Object.entries(s.provenance_counts||{}).map(([k,v])=>k+': '+v).join(' · ')}.`,
            'Cached outputs are not fresh requests. Textual error rates do not establish semantic or clinical correctness.'].filter(Boolean).join(' ');
        $('exportBtn').disabled=!cases.length;
        $('exportJson').disabled=!cases.length; $('exportCsv').disabled=!cases.length;
        const warnings=s.read_warnings||[];
        if(warnings.length){$('overviewError').textContent=`${warnings.length} saved file warning(s): `+warnings.map(w=>w.message).join(' ');$('overviewError').classList.remove('hidden');}
        ['pairA','pairB'].forEach((id,i)=>{
            $(id).innerHTML=(p.options||[]).map(o=>`<option value="${esc(o.key)}">${esc(o.label)}</option>`).join('')||'<option>No scored configuration</option>';
            if(p.keys?.[i])$(id).value=p.keys[i];
            $(id).disabled=boot.offline||(p.options||[]).length<2;
        });
        $('pairNote').textContent = p.flagged
            ? `${p.matched} shared cases · ${p.flagged} need reference review. Averages are provisional.`
            : p.matched ? `${p.matched} shared cases · ${viewLabel(state.view)} · same inputs and references.`
            : 'No shared successful cases yet. Saved attempts remain below.';
        $('comparisonDetails').textContent = (p.notes || []).join(' ');
        $('chartScopeLabel').textContent = `${p.matched || 0} shared cases · Corpus rates and per-case values`;
        renderModelScorecards(p);
        $('pairNote').classList.toggle('needs-attention',!!p.flagged);
        $('pairScope').textContent=p.matched ? `${p.matched} shared cases · ${p.models?.[0]?.reference_words||0} reference words per model` : 'No shared successful cases for this pair';
        $('pairedValues').innerHTML=(p.cases||[]).flatMap(c=>[c.left,c.right].map(row=>`<tr><td><button class="text-button" data-case="${esc(row.case_id)}" data-run="${esc(row.run_id)}" data-model="${esc(row.provider_key)}">Input ${row.audio_number||'text'} · ${esc(row.source_type)}<br>ref ${esc(row.reference_id.slice(-6))}</button></td><td>${esc(row.label)}</td><td>${percent(row.wer)}</td><td>${percent(row.cer)}</td><td>${row.counts.S} / ${row.counts.D} / ${row.counts.I}</td><td>${row.reference_words}</td><td>${c.needs_review?'Review reference':'No automatic flag'}</td></tr>`)).join('')||'<tr><td colspan="7">No chart values yet. Historical outputs remain in the case list.</td></tr>';
    }
    function renderModelScorecards(pair) {
        const models = pair.models || [];
        $('modelScorecards').innerHTML = [0,1].map(side => {
            const m = models[side], scored = !!(m && m.successes > 0);
            const count = key => scored ? Number(m.counts[key]).toLocaleString('en-US') : '—';
            const name = m?.label || (side ? 'Model B' : 'Model A');
            return `<article class="model-scorecard side-${side}" aria-label="${esc(name)} scorecard">
              <header><span class="model-side">${side ? 'B' : 'A'}</span><div><h3>${esc(name)}</h3><p>${scored ? `${m.successes} shared cases · ${viewLabel(state.view)}` : 'Awaiting shared successful cases'}</p></div>${pair.flagged ? '<span class="badge partial">Review needed</span>' : ''}</header>
              <div class="average-rates"><div><small>Average WER</small><strong data-stat="mean-wer">${percent(scored ? m.mean_case_wer : null)}</strong></div><div><small>Average CER</small><strong data-stat="mean-cer">${percent(scored ? m.mean_case_cer : null)}</strong></div></div>
              <div class="word-edit-totals" aria-label="Total word edits"><div><small>S <span>Substitutions</span></small><b data-stat="S">${count('S')}</b></div><div><small>D <span>Deletions</span></small><b data-stat="D">${count('D')}</b></div><div><small>I <span>Insertions</span></small><b data-stat="I">${count('I')}</b></div></div>
              <footer><span>Corpus · weighted</span><b>WER ${percent(scored ? m.wer : null)}</b><b>CER ${percent(scored ? m.cer : null)}</b></footer>
            </article>`;
        }).join('');
    }
    function renderCharts(){
        const p=state.summary.comparison||{};
        window.ASRCharts.bars($('modelChart'),p.models||[]);
        window.ASRCharts.paired($('caseChart'),p.cases||[],p.models||[]);
        $('seriesCount').textContent=(p.matched||0)+' SHARED CASES';
        $('seriesNote').textContent='Each row is one input + scored reference. Values over 100% are valid and are not clipped. Exact values are also in the table below.';
    }
    function getAudioCases(summary) {
        if (Array.isArray(summary?.audio_cases)) return summary.audio_cases;
        // Backward compatibility for saved standalone reports.
        const grouped = new Map();
        for (const r of summary?.rows || []) {
            const run = r.run_id || boot.job?.run_id || '', key = run + '/' + r.case_id;
            if (!grouped.has(key)) grouped.set(key, {...r, run_id: run, models: [], status: 'complete'});
            const c = grouped.get(key); c.models.push({...r, run_id: run, provider_key: r.provider_key || r.model});
            if (r.status !== 'success') c.status = 'partial';
        }
        for (const r of summary?.case_failures || []) {
            const run = r.run_id || boot.job?.run_id || '', key = run + '/' + r.case_id;
            if (!grouped.has(key)) grouped.set(key, {...r, run_id: run, models: [], status: 'failed'});
        }
        return [...grouped.values()];
    }
    function caseIssues(c) {
        const issues = [];
        const add = (kind, message) => {
            message = String(message || '').trim();
            if (!message || issues.some(x => x.message === message)) return;
            issues.push({kind, message});
        };
        if (c.review?.status === 'excluded') add('excluded', c.review?.note || 'Excluded from paired comparison. Saved scores remain available.');
        if (c.review?.status !== 'confirmed') (c.quality_flags || []).forEach(flag => add('review', flag.message));
        if (c.error?.message) add('audio', c.error.message);
        (c.models || []).forEach(model => {
            if (model.status !== 'success' && model.error?.message) add('model', `${model.label || model.provider_key || 'Model'}: ${model.error.message}`);
        });
        return issues;
    }
    function caseIssueMarkup(c) {
        const labels = {review:'Reference', audio:'Audio', model:'Model', excluded:'Excluded'};
        const issues = caseIssues(c);
        if (!issues.length) return '';
        return `<details class="case-issues" aria-label="Issues for this evaluation"><summary>${issues.length} issue${issues.length === 1 ? '' : 's'} · ${esc([...new Set(issues.map(i => labels[i.kind] || 'Issue'))].join(' / '))}</summary>${issues.map(i => `<div class="case-issue ${esc(i.kind)}"><span>${esc(labels[i.kind] || 'Issue')}</span><p>${esc(i.message)}</p></div>`).join('')}</details>`;
    }
    function caseMarkup(c, index) {
        const rid = esc(c.run_id), cid = esc(c.case_id);
        const models = (c.models || []).map(m => `<button type="button" class="case-model" data-case="${cid}" data-run="${rid}" data-model="${esc(m.provider_key || m.model)}" aria-label="Inspect ${esc(m.label)} for ${esc(c.title)}"><span class="case-model-name">${esc(m.label)}</span><span class="case-model-metrics"><span><small>WER</small><b>${percent(m.wer)}</b></span><span><small>CER</small><b>${percent(m.cer)}</b></span></span><span class="case-model-state ${m.status === 'success' ? 'ok' : ''}">${esc(m.status === 'success' ? 'Scored' : m.status)}${m.excluded ? ' · excluded' : m.latest === false ? ' · earlier attempt' : ''}${m.cache_hit ? ' · cached' : ''}</span></button>`).join('') || `<p class="no-models">${esc(c.error?.message || 'No model output saved for this case yet. Open for details.')}</p>`;
        const action = c.has_result === false ? (boot.offline ? '' : `data-open-run="${rid}"`) : `data-case="${cid}" data-run="${rid}"`;
        return `<article class="audio-case" tabindex="0" role="button" ${action} aria-label="Open audio ${index + 1}: ${esc(c.title)}"><div class="case-number">${String(index + 1).padStart(2,'0')}</div><div class="case-main"><div class="case-title"><b dir="auto">${esc(c.title)}</b>${c.review?.status==='excluded'?'<span class="badge partial">Excluded from comparison</span>':c.quality_flags?.length&&c.review?.status!=='confirmed'?'<span class="badge partial">Reference review</span>':''}<span class="badge ${esc(c.status)}">${esc(c.status)}</span></div><p>${c.audio_number ? 'Input '+c.audio_number+' · '+esc(c.source_type)+' · ' : ''}${c.duration == null ? 'Duration not recorded' : duration(c.duration)} · ${esc(({ar:'Arabic',en:'English',mixed:'Arabic + English'})[c.language] || c.language || 'Language not recorded')}</p><small>${esc(dateLabel(c.created_at))} · ${esc(c.case_id)} · run ${esc(c.run_id.slice(-6))}</small></div><div class="case-models">${models}</div><span class="case-chevron" aria-hidden="true">↗</span>${caseIssueMarkup(c)}</article>`;
    }
    function renderCaseList(summary, isRun = false) {
        const cases = getAudioCases(summary), size = 25, key = isRun ? 'runTablePage' : 'tablePage';
        const ids = isRun ? ['runCasesBody','runCaseCount','runTableFoot','runTablePaging'] : ['resultsBody','rowCount','tableFoot','tablePaging'];
        const pages = Math.max(1, Math.ceil(cases.length / size));
        state[key] = Math.min(state[key], pages - 1);
        const start = state[key] * size;
        $(ids[1]).textContent = cases.length;
        $(ids[0]).innerHTML = cases.slice(start,start+size).map((c,i) => caseMarkup(c,start+i)).join('') || `<div class="empty-state"><b>${!isRun && $('tableSearch').value.trim() ? 'No matching audio cases' : 'No saved case results'}</b>${isRun ? 'Run metadata exists, but no case output was saved. Its status is shown above; no score has been invented.' : 'Create an evaluation or open Sample results. Failed and incomplete saved cases also appear here.'}</div>`;
        $(ids[2]).textContent = `${cases.length ? start + 1 : 0}–${Math.min(cases.length,start+size)} of ${cases.length} audio evaluations · each card includes all model results`;
        $(ids[3]).innerHTML = pages > 1 ? `<button class="text-button" data-list-page="${isRun ? 'run' : 'overview'}" data-delta="-1" ${state[key]===0 ? 'disabled' : ''}>← Previous</button><span>${state[key]+1} / ${pages}</span><button class="text-button" data-list-page="${isRun ? 'run' : 'overview'}" data-delta="1" ${state[key]===pages-1 ? 'disabled' : ''}>Next →</button>` : '';
    }
    function renderTable() { if (state.summary) renderCaseList(state.summary); }
    async function openRun(id, keepPage = false) {
        if (boot.offline) return false;
        const ticket = ++state.runRequestId;
        state.selectedRun = id;
        if (!keepPage) { state.runTablePage=0; showPage('run'); }
        $('savedRunTitle').textContent = 'Loading run…';
        $('savedRunMeta').textContent = id;
        $('savedRunError').classList.add('hidden');
        $('runCasesBody').innerHTML = '<div class="empty-state">Loading saved audio cases…</div>';
        $('runExportBtn').disabled = $('runRescoreBtn').disabled = true;
        try {
            const result = await api('/api/results/' + encodeURIComponent(id) + '?view=' + state.runView);
            if (ticket !== state.runRequestId) return false;
            state.savedJob = result.job; state.runSummary = result.summary;
            $('savedRunTitle').textContent = result.job.name || id;
            $('savedRunMeta').textContent = `${dateLabel(result.job.created_at)} · ${result.job.status} · ${id}${result.job.stage ? ' · ' + result.job.stage : ''}`;
            document.querySelectorAll('[data-run-view]').forEach(b => b.classList.toggle('active', b.dataset.runView===state.runView));
            renderCaseList(result.summary,true);
            const hasCases = getAudioCases(result.summary).some(c => c.has_result !== false);
            $('runExportBtn').disabled = !hasCases;
            $('runRescoreBtn').disabled = !hasCases || !!result.job.metadata_missing;
            if (result.summary.read_warnings?.length) {
                $('savedRunError').textContent = 'Some saved files could not be read. The remaining cases are shown; existing files were not removed.';
                $('savedRunError').classList.remove('hidden');
            }
            return true;
        } catch (e) {
            if (ticket !== state.runRequestId) return false;
            $('savedRunTitle').textContent = 'Could not open this run';
            $('savedRunError').textContent = e.message;
            $('savedRunError').classList.remove('hidden');
            $('runCasesBody').innerHTML = '<div class="empty-state">Return to Saved runs and retry. Your saved files have not been deleted.</div>';
            $('runCaseCount').textContent = '—'; $('runTableFoot').textContent = ''; $('runTablePaging').replaceChildren();
            return false;
        }
    }
    async function openDetail(id, model, runId) {
        const run = runId || state.run;
        const ticket = ++state.detailRequestId;
        const result = boot.offline ? boot.cases.find(c => c.case_id === id && c.run_id === run) :
            await api(`/api/results/${encodeURIComponent(run)}/${encodeURIComponent(id)}`);
        if (ticket !== state.detailRequestId) return;
        if (!result) throw new Error('This result is not included in the exported scope.');
        state.detail = result; state.detailTab = 'words'; state.detailPage = 0; state.typeFilter = 'all';
        $('detailTitle').textContent = result.title;
        $('detailMeta').textContent = `${result.case_id} · ${run} · ${duration(result.audio?.duration)} · ${result.status}`;
        $('detailModel').innerHTML = result.models.map(m => `<option value="${esc(m.key)}">${esc(m.label)}</option>`).join('');
        if (model && result.models.some(m => m.key === model)) $('detailModel').value = model;
        $('detailScoreView').value = state.page === 'run' ? state.runView : state.view;
        $('detailAudio').pause();
        if (boot.offline || !result.audio?.duration) {
            $('detailAudio').removeAttribute('src'); $('detailAudio').classList.add('hidden');
        } else {
            $('detailAudio').src = `/api/audio/${encodeURIComponent(run)}/${encodeURIComponent(id)}`;
            $('detailAudio').classList.remove('hidden');
        }
        if (!$('detailDialog').open) $('detailDialog').showModal();
        renderReview();
        renderDetail();
    }
    function renderDetail() {
        const c = state.detail, m = c.models.find(m => m.key === $('detailModel').value) || c.models[0];
        document.querySelectorAll('[data-detail]').forEach(b => b.classList.toggle('active', b.dataset.detail === state.detailTab));
        if(state.detailTab==='original') {
            $('detailContent').innerHTML=comparePanels(c.reference,m?.raw_text??m?.speech_text??'No transcript was saved.','Ground truth · original','Model output · original',false);
            if(!m||m.status!=='success')$('detailSummary').innerHTML='';
            return;
        }
        if(state.detailTab==='trace') {
            $('detailContent').innerHTML=`<pre class="mono">${esc(JSON.stringify({run_id:c.run_id,case_id:c.case_id,source:c.source,source_metadata:c.source_metadata,audio:c.audio,status:c.status,error:m?.error||c.error,review:c.report_review,request_settings:m?.request_settings,provenance:m?.provenance,trace:c.trace},null,2))}</pre>`;
            return;
        }
        if (!m || m.status !== 'success' || !m.evaluation?.metrics?.[$('detailScoreView').value]) {
            $('detailSummary').innerHTML = '';
            $('detailContent').innerHTML = `<div class="empty-state"><b>No score</b>${esc(m?.error?.message || c.error?.message || 'This case did not produce a transcript.')}<p>Provider or media failures are not empty ASR predictions.</p></div>`;
            return;
        }
        const e = m.evaluation, v = e.metrics[$('detailScoreView').value], counts = v.words.counts;
        $('detailSummary').innerHTML = [['WER', percent(v.wer)], ['CER', percent(v.cer)], ['Correct', counts.C], ['Substitutions', counts.S], ['Deletions', counts.D], ['Insertions', counts.I]].map(([k, val]) => `<div class="detail-stat"><small>${k}</small><b>${val}</b></div>`).join('');
        if (e.warnings?.length && $('detailScoreView').value === 'normalized')
            $('detailSummary').innerHTML += '<p class="detail-note" style="grid-column:1/-1">Cleaning applies spelling equivalences and may hide real word differences.</p>';
        const tab = state.detailTab;
        if (tab === 'original') {
            $('detailContent').innerHTML = comparePanels(c.reference, m.raw_text, 'Ground truth · original', 'Provider output · original', false) + `<p class="detail-note">Original text is retained. Subtitle metadata is excluded only from the scoring copy. Provenance: ${esc(m.provenance)}.</p>`;
            return;
        }
        if (tab === 'normalization' && $('detailScoreView').value === 'raw') {
            $('detailContent').innerHTML = '<p class="detail-note">No cleaning. Spelling, letter case and vowel marks are not normalized. Display characters and spacing are prepared for comparison.</p>';
            return;
        }
        if (tab === 'normalization') {
            $('detailContent').innerHTML = `<p class="detail-note">Cleaning rules ${esc(e.normalizer_version)} · Applied to both texts. Original text is unchanged.</p>` + ['reference', 'prediction'].map(side => `<section class="normalization-card"><h3>${side === 'reference' ? 'Ground truth' : 'Prediction'}</h3>${Object.entries(e.changes[side]).map(([k, d]) => `<p><b>${esc(k)}</b> · ${d.count} change(s)<br>${d.examples.map(x => `<span class="change-pair" dir="ltr"><bdi dir="auto">${esc(x.from || '∅')}</bdi><span> → </span><bdi dir="auto">${esc(x.to || '∅')}</bdi></span>`).join(' · ')}</p>`).join('') || '<p>No policy changes.</p>'}</section>`).join('') + `<p class="detail-note">${esc(e.note)}</p>`;
            return;
        }
        if (tab === 'trace') {
            const data = { run_id: c.run_id, case_id: c.case_id, source: c.source, source_metadata: c.source_metadata, audio: c.audio, reference_hash: c.reference_hash, profile_id: e.profile_id, engine: v.words.engine, model: m.label, provenance: m.provenance, cache_hit: m.cache_hit, received_at: m.received_at, api_elapsed_ms: m.elapsed_ms, request_settings: m.request_settings, trace: c.trace };
            $('detailContent').innerHTML = `<pre class="mono">${esc(JSON.stringify(data, null, 2))}</pre><p class="detail-note">API elapsed time includes transfer and service waiting; it is not pure inference time. WER/CER are lexical metrics, not clinical accuracy.</p>`;
            return;
        }
        const metric = v[tab], allOps = metric.operations;
        const visible = allOps.map((o, i) => ({ ...o, _i: i })).filter(o => state.typeFilter === 'all' || o.type === state.typeFilter);
        const pageSize = tab === 'characters' ? 500 : 300, totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
        state.detailPage = Math.min(state.detailPage, totalPages - 1);
        const ops = visible.slice(state.detailPage * pageSize, (state.detailPage + 1) * pageSize);
        const charMode = tab === 'characters';
        function tokens(side) { return ops.map(o => { const t = o[side]; const text = t ? (charMode && t.text === ' ' ? '␠' : t.text) : '∅'; return `<span class="token ${o.type} ${t ? '' : 'placeholder'}" data-token="${o._i}" title="${o.type} · ${t ? `source [${t.source_start}, ${t.source_end})` : 'no counterpart'}">${esc(text)}</span>${charMode ? '' : ' '}`; }).join(''); }
        $('detailContent').innerHTML = `<div class="alignment-tools"><div class="legend"><span class="C">Correct</span><span class="S">Substitution</span><span class="D">Deletion</span><span class="I">Insertion</span></div><select id="errorType" aria-label="Edit type"><option value="all">All operations</option><option value="C">Correct</option><option value="S">Substitutions</option><option value="D">Deletions</option><option value="I">Insertions</option></select></div>` + comparePanels(tokens('reference'), tokens('prediction'), 'Ground truth · ' + viewLabel($('detailScoreView').value), 'Prediction · ' + viewLabel($('detailScoreView').value), true, charMode) +
            (totalPages > 1 ? `<div class="pagination"><button class="text-button" id="diffPrev" ${state.detailPage === 0 ? 'disabled' : ''}>← Previous</button><span>${state.detailPage + 1} / ${totalPages}</span><button class="text-button" id="diffNext" ${state.detailPage === totalPages - 1 ? 'disabled' : ''}>Next →</button></div>` : '') +
            `<p class="detail-note">${metric.reference_length} reference ${charMode ? 'characters' : 'words'} · ${metric.prediction_length} predicted · ${esc(metric.engine)}. ${charMode ? '␠ marks a scored space.' : 'Differences are tied to positions, including repeated words.'}</p>` +
            `<div class="diff-table"><table><thead><tr><th>Type</th><th>Reference</th><th>Prediction</th><th>Position</th></tr></thead><tbody>${ops.filter(o => o.type !== 'C').map(o => `<tr data-op="${o._i}"><td><span class="edit-count ${o.type}">${({ S: 'Substitution', D: 'Deletion', I: 'Insertion' })[o.type]}</span></td><td dir="auto">${esc(o.reference?.text ?? '—')}</td><td dir="auto">${esc(o.prediction?.text ?? '—')}</td><td>${o.ref_index === null ? '—' : o.ref_index + 1} / ${o.hyp_index === null ? '—' : o.hyp_index + 1}</td></tr>`).join('') || '<tr><td colspan="4">No errors in this view.</td></tr>'}</tbody></table></div>`;
        $('errorType').value = state.typeFilter;
        $('errorType').onchange = () => { state.typeFilter = $('errorType').value; state.detailPage = 0; renderDetail(); };
        if ($('diffPrev'))
            $('diffPrev').onclick = () => { state.detailPage--; renderDetail(); };
        if ($('diffNext'))
            $('diffNext').onclick = () => { state.detailPage++; renderDetail(); };
    }
    function renderReview(){
        const c=state.detail;
        $('reviewEditor').open=!!c.quality_flags?.length;
        $('correctedReference').value=c.reference||'';
        $('correctedConfirmed').checked=false;
        $('reviewStatus').textContent=[c.report_review?.status?'Review: '+c.report_review.status:'Not manually reviewed.', ...(c.quality_flags||[]).map(x=>x.message), boot.offline?'Offline snapshot: review changes are available in the running app.':'Review actions never send audio.'].join(' ');
        ['markConfirmed','markExcluded','clearReview','correctedReference','correctedConfirmed','saveReference'].forEach(id=>$(id).disabled=!!boot.offline);
    }
    async function recordReview(status){
        const c=state.detail;
        if(!c||boot.offline)return;
        if(status==='excluded'&&!confirm('Exclude this saved case from aggregate comparisons? It will remain visible with its original scores.'))return;
        try{
            const review=await api(`/api/reviews/${encodeURIComponent(c.run_id)}/${encodeURIComponent(c.case_id)}`,{method:'POST',body:{status,note:status==='excluded'?'Excluded by user during reference review.':''}});
            c.report_review=review;renderReview();await selectRun('all');toast('Review saved. Original results unchanged.');
        }catch(e){toast(e.message,true);}
    }
    function comparePanels(a, b, ah, bh, isHTML, charMode = false) { return `<div class="compare-grid"><section class="compare-panel"><div class="compare-title">${esc(ah)}</div><div class="transcript ${charMode ? 'characters' : ''}" dir="auto">${isHTML ? a : esc(a)}</div></section><section class="compare-panel"><div class="compare-title">${esc(bh)}</div><div class="transcript ${charMode ? 'characters' : ''}" dir="auto">${isHTML ? b : esc(b)}</div></section></div>`; }
    async function refreshHealth() { const h = await api('/api/health'); $('healthLabel').textContent = (h.tools.ffmpeg && h.tools.ffprobe ? 'Media tools ready' : 'Check system readiness') + ' · v' + h.version; $('humainReady').classList.toggle('ready', h.providers.humain); $('elevenReady').classList.toggle('ready', h.providers.elevenlabs); }
    async function submitEvaluation(event) {
        event.preventDefault();
        $('formError').textContent = '';
        $('runButton').disabled = true;
        try {
            if (state.rescore) {
                const j = await api('/api/rescore/' + encodeURIComponent(state.rescore), { method: 'POST', body: { profile: profile(), score_view: selectedScoreView() } });
                state.rescore = null;
                await followSubmittedRun(j, selectedScoreView());
                return;
            }
            if(state.source!=='batch'&&!$('referenceConfirmed').checked)throw new Error('Check the reference for this audio and tick the reference confirmation.');
            let cases;
            if (state.source === 'batch') {
                const manifest = $('manifestFile').files[0];
                if (!manifest)
                    throw new Error('Select a JSON manifest.');
                if (manifest.size > 2 * 1024 ** 2)
                    throw new Error('Manifest is larger than 2 MB.');
                const parsed = JSON.parse(await manifest.text());
                cases = Array.isArray(parsed) ? parsed : parsed.cases;
                if (!Array.isArray(cases))
                    throw new Error('Manifest must contain a cases array.');
                const files = [...$('batchFiles').files];
                if (files.length) {
                    if (new Set(files.map(f => f.name)).size !== files.length)
                        throw new Error('Uploaded filenames must be unique in a batch.');
                    const uploaded = [];
                    for (let i = 0; i < files.length; i++) {
                        $('runButton').textContent = `Uploading ${i + 1} / ${files.length}…`;
                        const form = new FormData();
                        form.append('files', files[i]);
                        uploaded.push(...(await api('/api/uploads', { method: 'POST', body: form, long: true })).uploads);
                    }
                    for (const c of cases) {
                        if (c.source?.type === 'upload' && c.source.filename) {
                            const u = uploaded.find(u => u.display_name === c.source.filename);
                            if (!u)
                                throw new Error('Missing uploaded file: ' + c.source.filename);
                            c.source = { type: 'upload', upload_id: u.upload_id };
                        }
                    }
                }
            }
            else {
                let source = { type: state.source };
                if (state.source === 'upload') {
                    const f = $('audioFile').files[0];
                    if (!f)
                        throw new Error('Select an audio file.');
                    const form = new FormData();
                    form.append('files', f);
                    source.upload_id = (await api('/api/uploads', { method: 'POST', body: form, long: true })).uploads[0].upload_id;
                }
                if (state.source === 'youtube')
                    source.url = $('youtubeUrl').value.trim();
                cases = [{ case_id: 'case_001', title: $('caseTitle').value, source, ground_truth: $('groundTruth').value, reference_confirmed: $('referenceConfirmed').checked, crop: { start: Number($('cropStart').value || 0), end: $('cropEnd').value === '' ? null : Number($('cropEnd').value) } }];
            }
            if ($('suppliedMode').checked) {
                if (state.source === 'batch')
                    throw new Error('Supplied transcript mode accepts one case. Batch JSON here is for audio/API evaluations.');
                const predictions = [
                    { label: $('suppliedLabel1').value.trim() || 'Model 1', text: $('suppliedText1').value },
                    { label: $('suppliedLabel2').value.trim() || 'Model 2', text: $('suppliedText2').value }
                ];
                if (predictions.some(x => !x.text.trim()))
                    throw new Error('Paste both supplied transcripts.');
                const j = await api('/api/imported/evaluate', { method: 'POST', body: { case: cases[0], predictions, profile: profile(), score_view: selectedScoreView() } });
                await followSubmittedRun(j, selectedScoreView());
                // followSubmittedRun opens synchronous imported results as well.
                return;
            }
            if (state.source === 'sample' && !boot.sample_audio_present) throw new Error('The saved demo has no audio file in the public repository. Select Upload or YouTube for live ASR, or click View sample results for the text-only demo.');
            const models = [];
            if ($('selectHumain').checked)
                models.push('humain');
            if ($('selectEleven').checked)
                models.push('elevenlabs');
            const providerCredentials = {};
            if ($('humainApiKey').value.trim()) providerCredentials.humain_api_key = $('humainApiKey').value.trim();
            if ($('humainApiUrl').value.trim()) providerCredentials.humain_api_url = $('humainApiUrl').value.trim();
            if ($('elevenApiKey').value.trim()) providerCredentials.elevenlabs_api_key = $('elevenApiKey').value.trim();
            const j = await api('/api/evaluate', { method: 'POST', body: { provider_credentials: providerCredentials, name: cases.length === 1 ? cases[0].title : `Batch · ${cases.length} clips`, cases, models, profile: profile(), score_view: selectedScoreView(), consent: $('consent').checked, reuse_cache: $('reuseCache').checked } });
            $('humainApiKey').value = ''; $('elevenApiKey').value = '';
            await followSubmittedRun(j, selectedScoreView());
        }
        catch (e) {
            $('formError').textContent = e.message;
            if (state.page === 'new') jumpTo('formError');
        }
        finally {
            $('runButton').disabled = false;
            $('runButton').textContent = state.rescore ? 'Re-score without API calls →' : $('suppliedMode').checked ? 'Score supplied transcripts →' : 'Run evaluation →';
        }
    }
    function downloadLocal(name, content, type = 'application/json') { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1500); }
    for(const id of ['youtubeUrl','audioFile','cropStart','cropEnd','groundTruth']){
        $(id).addEventListener(id==='audioFile'?'change':'input',()=>{
            $('referenceConfirmed').checked=false;
            $('referenceGuard').textContent='Input or reference changed. Check the audio/reference match before running.';
            if(id==='audioFile'&&$('audioFile').files[0]&&!$('caseTitle').value)$('caseTitle').value=$('audioFile').files[0].name;
        });
    }
    for(const id of ['pairA','pairB'])$(id).addEventListener('change',async()=>{
        if($('pairA').value===$('pairB').value){toast('Choose two different model configurations.',true);return;}
        state.pair=[$('pairA').value,$('pairB').value];await selectRun('all');
    });
    $('markConfirmed').onclick=()=>recordReview('confirmed');
    $('markExcluded').onclick=()=>recordReview('excluded');
    $('clearReview').onclick=()=>recordReview('unreviewed');
    $('saveReference').onclick=async()=>{
        if(!$('correctedConfirmed').checked){toast('Confirm you reviewed the corrected reference against the audio.',true);return;}
        const c=state.detail;const button=$('saveReference');button.disabled=true;
        try{
            const j=await api(`/api/reference/${encodeURIComponent(c.run_id)}/${encodeURIComponent(c.case_id)}`,{method:'POST',body:{reference:$('correctedReference').value,confirmed:true},long:true});
            $('detailDialog').close();await loadJobs();await selectRun('all');await openRun(j.run_id);toast('New evaluation saved without an ASR call. The original remains in history.');
        }catch(e){toast(e.message,true);}finally{button.disabled=false;}
    };
    $('exportJson').onclick=()=>{if(boot.offline)downloadLocal('asr_results.json',JSON.stringify({exported_at:boot.exported_at,cases:boot.cases,summary:state.summary},null,2));else location.href='/api/export/overview.json?'+scopeQuery();};
    $('exportCsv').onclick=()=>{
        if(boot.offline){
            if(boot.csv?.[state.view])downloadLocal('asr_results.csv',boot.csv[state.view],'text/csv;charset=utf-8');
            else toast('CSV data is not included in this older export. Export a fresh report from the app.',true);
        }else location.href='/api/export/overview.csv?'+scopeQuery();
    };
    document.addEventListener('click', async (e) => {
        if (e.target.closest('.case-issues')) return;
        const jump = e.target.closest('[data-jump]');
        if (jump) { jumpTo(jump.dataset.jump); return; }
        const page = e.target.closest('[data-page]');
        if (page) {
            if (page.dataset.page !== 'overview') disarmFollow();
            if (page.dataset.page === 'new')
                state.rescore = null;
            showPage(page.dataset.page);
            if (page.dataset.page === 'overview') {if (!boot.offline) clearScopeInputs(); await selectRun(boot.offline ? boot.job.run_id : 'all');}
        }
        const src = e.target.closest('[data-source]');
        if (src)
            sourceTab(src.dataset.source);
        const view = e.target.closest('[data-view]');
        if (view) {
            state.view = view.dataset.view;
            document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
            if (state.run)
                try {
                    await selectRun(state.run);
                }
                catch (err) {
                    toast(err.message, true);
                }
        }
        const row = e.target.closest('[data-case]');
        if (row)
            try {
                disarmFollow();
                await openDetail(row.dataset.case, row.dataset.model, row.dataset.run);
            }
            catch (err) {
                toast(err.message, true);
            }
        const open = e.target.closest('[data-open-run]');
        if (open) {
            disarmFollow();
            try {
                await openRun(open.dataset.openRun);
            }
            catch (err) {
                toast(err.message, true);
            }
        }
        const rv = e.target.closest('[data-run-view]');
        if (rv && state.selectedRun) { state.runView=rv.dataset.runView; await openRun(state.selectedRun,true); }
        const paging = e.target.closest('[data-list-page]');
        if (paging && !paging.disabled) {
            const run = paging.dataset.listPage === 'run', key = run ? 'runTablePage' : 'tablePage';
            state[key] += Number(paging.dataset.delta);
            renderCaseList(run ? state.runSummary : state.summary,run);
            jumpTo(run ? 'runResultsSection' : 'audioCasesSection');
        }
        const tab = e.target.closest('[data-detail]');
        if (tab) {
            state.detailTab = tab.dataset.detail;
            state.detailPage = 0;
            state.typeFilter = 'all';
            renderDetail();
        }
        const op = e.target.closest('[data-op],[data-token]');
        if (op) {
            const n = op.dataset.op ?? op.dataset.token;
            document.querySelectorAll('.token').forEach(t => t.classList.toggle('selected', t.dataset.token === n));
            document.querySelector(`.token[data-token="${n}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    });
    $('chartsSection').addEventListener('toggle', () => { if ($('chartsSection').open && state.summary) renderCharts(); });
    $('openCompletedRun').onclick = () => openCompletedResult().catch(e => toast(e.message, true));
    $('dismissCompletion').onclick = () => $('completionNotice').classList.add('hidden');
    document.querySelectorAll('.export-menu button').forEach(button => button.addEventListener('click', () => { button.closest('details').open=false; }));
    $('evalForm').addEventListener('submit', submitEvaluation);
    document.addEventListener('keydown', e => {
        if (e.target instanceof Element && e.target.matches('.audio-case,svg [data-case]') && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault(); e.target.dispatchEvent(new MouseEvent('click', {bubbles:true}));
        }
    });
    let searchTimer;
    function refreshScope() { state.tablePage=0; selectRun('all'); }
    $('tableSearch').oninput = () => {clearTimeout(searchTimer); state.requestId++; $('exportBtn').disabled=true; searchTimer=setTimeout(refreshScope,250);};
    $('clearFilters').onclick = () => {clearTimeout(searchTimer); clearScopeInputs(); selectRun('all');};
    $('refreshOverview').onclick = refreshScope;
    $('detailModel').onchange = () => { state.detailPage = 0; renderDetail(); };
    $('detailScoreView').onchange = () => { state.detailPage = 0; renderDetail(); };
    $('closeDetail').onclick = () => { $('detailAudio').pause(); $('detailDialog').close(); };
    $('detailDialog').addEventListener('close', () => $('detailAudio').pause());
    $('suppliedMode').onchange = () => setSuppliedMode($('suppliedMode').checked);
    document.querySelectorAll('[data-open-sample]').forEach(button => button.addEventListener('click', openSampleResults));
    $('exportBtn').onclick = () => { if (state.lastQuery) window.location.href = '/api/export/overview?' + state.lastQuery; };
    $('printBtn').onclick = () => window.print();
    $('runExportBtn').onclick = () => {
        if (state.selectedRun) window.location.href = '/api/export/overview?' + new URLSearchParams({run: state.selectedRun,view: state.runView});
    };
    $('runRescoreBtn').onclick = () => {
        if (!state.selectedRun || !state.savedJob) return;
        setSuppliedMode(false); state.rescore=state.selectedRun;
        setProfile(state.savedJob.profile || {}); setScoreMode(state.runView); showPage('new');
        $('newTitle').textContent = 'Re-score saved transcripts.';
        $('newSubtitle').textContent = 'Uses saved transcripts. No ASR API calls.';
        for (const id of ['sourceCard','referenceCard','modelsCard','consentLabel']) $(id).classList.add('hidden');
        $('runButton').textContent = 'Re-score without API calls →';
    };
    $('stopJob').onclick = async () => { if (!state.activeJob) return; try {
        await api('/api/jobs/' + state.activeJob + '/cancel', { method: 'POST', body: {} });
        toast('Stop requested. The current case will finish first.');
    }
    catch (e) {
        toast(e.message, true);
    } };
    $('manifestTemplate').onclick = () => { const c = state.sample.case; downloadLocal('batch_manifest.json', JSON.stringify({ name: 'My ASR comparison', cases: [{ ...c, source: { type: 'youtube', url: state.sample.source.url }, reference_confirmed: false, crop: { start: 0, end: state.sample.audio.duration } }] }, null, 2)); };
    $('themeToggle').onclick = () => { document.body.classList.toggle('dark'); try {
        localStorage.setItem('asr-theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    }
    catch (_) { } };
    function applySample(sample) {
        if (!sample?.case?.ground_truth) throw new Error('Included reference is missing.');
        state.sample=sample;
        $('sampleDuration').textContent=duration(sample.audio?.duration);
    }
    async function init() {
        if (!boot.offline) {
            try {
                const follow = JSON.parse(sessionStorage.getItem('asr-follow-run'));
                if (follow && typeof follow.id === 'string' && /^(run|sample)_[a-zA-Z0-9]+$/.test(follow.id)) state.follow = follow;
            } catch (_) { /* Only this browser tab's pending evaluation is restored. */ }
        }
        try {
            if (localStorage.getItem('asr-theme') === 'dark')
                document.body.classList.add('dark');
        }
        catch (_) { }
        if (boot.offline) {
            document.body.classList.add('offline');
            ['markConfirmed','markExcluded','clearReview','correctedReference','correctedConfirmed','saveReference'].forEach(id=>{$(id).disabled=true;});
            $('workspaceMode').textContent = 'Offline report';
            $('workspaceNote').textContent = 'Saved result snapshot. No live API calls.';
            state.run = boot.job?.run_id || 'all';
            await loadJobs();
            $('tableSearch').disabled = $('clearFilters').disabled = true;
            if (boot.filters) $('tableSearch').value=boot.filters.q || '';
            await selectRun(state.run);
            return;
        }
        // Bootstrap carries the pinned reference; health never gates loading saved runs.
        if (boot.sample) {
            applySample(boot.sample); sourceTab(boot.sample_audio_present ? 'sample' : 'upload');
            setProfile(policyCatalog.cleaning_profile || state.sample.profile); $('language').value='ar';
        }
        const readiness=refreshHealth().catch(()=>{$('healthLabel').textContent='Readiness unavailable · UI 1.6.2';});
        const samples=api('/api/sample').then(applySample).catch(()=>{});
        await selectRun('all');
        await Promise.allSettled([readiness,samples]);
    }

    let chartResize;
    window.addEventListener('resize', () => {clearTimeout(chartResize); chartResize=setTimeout(()=>{if(state.summary) renderCharts();},100);});
    init().catch(e=>{console.error(e); showUiFailure(e.message);});
})();
