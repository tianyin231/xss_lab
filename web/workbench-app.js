import { PAGE_WORKBENCH_TEMPLATE } from './page-workbench-view-v2.js'

const { createApp, ref, computed, onMounted, watch } = Vue

createApp({
  setup() {
    const defaultApiBase = window.APP_CONFIG?.apiBase || 'http://127.0.0.1:5001/api'
    const apiBase = ref(localStorage.getItem('apiBase') || defaultApiBase)
    const jobs = ref([])
    const pages = ref([])
    const selectedJobId = ref('')
    const selectedPageUrl = ref('')
    const workbenchData = ref(null)
    const workbenchLoading = ref(false)
    const workbenchRetesting = ref(false)
    const workbenchRetestResults = ref([])
    const workbenchRetestFeedback = ref('')
    const selectedRetestReportId = ref('')
    const selectedCompareReportId = ref('')
    const deletingRetestResultId = ref('')
    const aiExplainAudience = ref('developer')
    const aiExplainLoading = ref(false)
    const aiExplainError = ref('')
    const aiExplainResult = ref('')
    const aiValidateMode = ref('standard')
    const aiValidateLoading = ref(false)
    const aiValidateError = ref('')
    const aiValidateResult = ref(null)
    const selectedAIMultiRoundReportId = ref('')
    const deletingAIMultiRoundReportId = ref('')
    const workbenchSelectedPreset = ref('__default__')
    const workbenchSelectedVector = ref('')
    const workbenchCustomPayload = ref('')

    const selectedJob = computed(() => jobs.value.find(item => item.id === selectedJobId.value) || null)
    const selectedPage = computed(() => pages.value.find(item => item.url === selectedPageUrl.value) || null)
    const currentRetestReport = computed(() => {
      const reports = workbenchData.value?.manual_retest_reports || []
      if (!reports.length) return null
      return reports.find(item => item.batch_id === selectedRetestReportId.value) || reports[0]
    })
    const compareCandidateReports = computed(() => {
      const reports = workbenchData.value?.manual_retest_reports || []
      return reports.filter(item => item.batch_id !== selectedRetestReportId.value)
    })
    const compareRetestReport = computed(() => {
      const reports = compareCandidateReports.value
      if (!reports.length) return null
      return reports.find(item => item.batch_id === selectedCompareReportId.value) || reports[0]
    })
    const currentAIMultiRoundReport = computed(() => {
      const reports = workbenchData.value?.ai_multi_round_reports || []
      return reports.find(item => item.batch_id === selectedAIMultiRoundReportId.value) || reports[0] || null
    })
    const retestComparison = computed(() => {
      const current = currentRetestReport.value
      const compare = compareRetestReport.value
      if (!current || !compare) return null

      const indexReport = report =>
        new Map(
          (report.results || []).map(item => [
            `${item.vector || ''}::${item.parameter_name || ''}`,
            item,
          ]),
        )

      const currentMap = indexReport(current)
      const compareMap = indexReport(compare)
      const keys = Array.from(new Set([...currentMap.keys(), ...compareMap.keys()])).sort()

      const changed = []
      const onlyCurrent = []
      const onlyCompare = []

      for (const key of keys) {
        const currentItem = currentMap.get(key)
        const compareItem = compareMap.get(key)
        if (currentItem && compareItem) {
          const levelChanged = currentItem.level !== compareItem.level
          const reflectionChanged = Boolean(currentItem.reflection_found) !== Boolean(compareItem.reflection_found)
          const contextChanged = (currentItem.reflection_context_label || '') !== (compareItem.reflection_context_label || '')
          if (levelChanged || reflectionChanged || contextChanged) {
            changed.push({
              key,
              label: `${currentItem.vector || compareItem.vector || '-'} / ${currentItem.parameter_name || compareItem.parameter_name || '-'}`,
              current: currentItem,
              compare: compareItem,
            })
          }
          continue
        }
        if (currentItem) {
          onlyCurrent.push({
            key,
            label: `${currentItem.vector || '-'} / ${currentItem.parameter_name || '-'}`,
            item: currentItem,
          })
        } else if (compareItem) {
          onlyCompare.push({
            key,
            label: `${compareItem.vector || '-'} / ${compareItem.parameter_name || '-'}`,
            item: compareItem,
          })
        }
      }

      return {
        changed,
        onlyCurrent,
        onlyCompare,
        summary: {
          changed: changed.length,
          onlyCurrent: onlyCurrent.length,
          onlyCompare: onlyCompare.length,
        },
      }
    })
    const workbenchRetestPayloadOptions = computed(() => {
      const options = [{ value: '__default__', label: '系统默认 Payload', payload: '', vector: '' }]
      for (const item of workbenchData.value?.payloads || []) {
        options.push({
          value: `suggested:${item.label}:${item.vector || ''}:${item.payload}`,
          label: item.vector ? `${item.label} (${item.vector})` : item.label,
          payload: item.payload || '',
          vector: item.vector || '',
        })
      }
      options.push({ value: '__custom__', label: '自定义 Payload', payload: '', vector: '' })
      return options
    })

    function formatDateTime(value) {
      if (value === null || value === undefined || value === '') return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return '-'
      return new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date).replace(/\//g, '-')
    }

    async function fetchJobs() {
      const res = await fetch(`${apiBase.value}/jobs`)
      jobs.value = await res.json()
    }

    async function fetchPages(jobId) {
      if (!jobId) {
        pages.value = []
        return
      }
      const res = await fetch(`${apiBase.value}/jobs/${jobId}/pages`)
      const body = await res.json()
      if (!res.ok) throw new Error(body.error || '获取页面列表失败')
      pages.value = body.pages || []
    }

    async function fetchWorkbenchUrl(jobId = '', pageUrl = '') {
      const params = new URLSearchParams()
      if (jobId) params.set('job_id', jobId)
      if (pageUrl) params.set('page_url', pageUrl)
      const suffix = params.toString() ? `?${params.toString()}` : ''
      const res = await fetch(`${apiBase.value}/workbench/url${suffix}`)
      const body = await res.json()
      if (!res.ok) throw new Error(body.error || '获取工作台地址失败')
      return body.url
    }

    async function fetchWorkbench(options = {}) {
      const { preserveRetestState = false, preferredBatchId = '' } = options
      if (!selectedJobId.value || !selectedPageUrl.value) {
        workbenchData.value = null
        return
      }
      workbenchLoading.value = true
      try {
        const endpoint = `${apiBase.value}/jobs/${selectedJobId.value}/pages/workbench?url=${encodeURIComponent(selectedPageUrl.value)}`
        const res = await fetch(endpoint)
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || '获取工作台数据失败')
        workbenchData.value = body
        if (!preserveRetestState) {
          resetRetestState()
        }
        syncRetestReportSelection(preferredBatchId)
      } finally {
        workbenchLoading.value = false
      }
    }

    function resetRetestState() {
      workbenchRetestResults.value = []
      workbenchRetestFeedback.value = ''
      aiExplainError.value = ''
      aiExplainResult.value = ''
      aiValidateError.value = ''
      aiValidateResult.value = null
      workbenchSelectedPreset.value = '__default__'
      workbenchSelectedVector.value = ''
      workbenchCustomPayload.value = ''
    }

    function syncRetestReportSelection(preferredBatchId = '') {
      const reports = workbenchData.value?.manual_retest_reports || []
      if (!reports.length) {
        selectedRetestReportId.value = ''
        selectedCompareReportId.value = ''
        selectedAIMultiRoundReportId.value = ''
        workbenchRetestResults.value = []
        if (!workbenchRetesting.value) {
          workbenchRetestFeedback.value = ''
        }
        return
      }
      const nextId =
        (preferredBatchId && reports.find(item => item.batch_id === preferredBatchId)?.batch_id) ||
        (selectedRetestReportId.value && reports.find(item => item.batch_id === selectedRetestReportId.value)?.batch_id) ||
        reports[0].batch_id
      selectedRetestReportId.value = nextId
      const compareCandidates = reports.filter(item => item.batch_id !== nextId)
      selectedCompareReportId.value =
        (selectedCompareReportId.value && compareCandidates.find(item => item.batch_id === selectedCompareReportId.value)?.batch_id) ||
        (compareCandidates[0]?.batch_id || '')
      const report = reports.find(item => item.batch_id === nextId) || reports[0]
      workbenchRetestResults.value = report.results || []
      const aiReports = workbenchData.value?.ai_multi_round_reports || []
      selectedAIMultiRoundReportId.value =
        (selectedAIMultiRoundReportId.value && aiReports.find(item => item.batch_id === selectedAIMultiRoundReportId.value)?.batch_id) ||
        (aiReports[0]?.batch_id || '')
      if (!workbenchRetesting.value) {
        workbenchRetestFeedback.value = `已加载 ${formatDateTime(report.created_at)} 的复测报告，共 ${report.result_count} 条结果。`
      }
    }

    function applyWorkbenchRetestPreset() {
      const option = workbenchRetestPayloadOptions.value.find(item => item.value === workbenchSelectedPreset.value)
      if (!option) return
      if (workbenchSelectedPreset.value !== '__custom__') {
        workbenchCustomPayload.value = ''
      }
      if (!workbenchSelectedVector.value && option.vector) {
        workbenchSelectedVector.value = option.vector
      }
    }

    async function copyToClipboard(text, successMessage = '已复制') {
      const value = String(text || '').trim()
      if (!value) return
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(value)
        } else {
          const textarea = document.createElement('textarea')
          textarea.value = value
          textarea.setAttribute('readonly', 'readonly')
          textarea.style.position = 'fixed'
          textarea.style.left = '-9999px'
          document.body.appendChild(textarea)
          textarea.select()
          document.execCommand('copy')
          textarea.remove()
        }
        window.alert(successMessage)
      } catch (err) {
        window.alert(`复制失败: ${err.message}`)
      }
    }

    function applySuccessfulPayload(item) {
      if (!item?.payload) return
      workbenchSelectedPreset.value = '__custom__'
      workbenchCustomPayload.value = item.payload
      workbenchSelectedVector.value = item.vector || ''
      workbenchRetestFeedback.value = '已带入动态验证成功的 payload，可直接开始复测。'
    }

    async function runWorkbenchRetest() {
      if (!selectedJobId.value || !workbenchData.value?.page?.url) return
      let payload = ''
      let vector = workbenchSelectedVector.value || ''
      const option = workbenchRetestPayloadOptions.value.find(item => item.value === workbenchSelectedPreset.value)
      if (workbenchSelectedPreset.value === '__custom__') {
        payload = workbenchCustomPayload.value.trim()
      } else if (option) {
        payload = option.payload || ''
        if (!vector && option.vector) vector = option.vector
      }

      workbenchRetesting.value = true
      workbenchRetestFeedback.value = '正在执行页面复测...'
      try {
        const res = await fetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/retest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: workbenchData.value.page.url,
            payload,
            vector,
          }),
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || '页面复测失败')
        workbenchRetestResults.value = body.results || []
        workbenchRetestFeedback.value = `页面复测完成，已生成 ${workbenchRetestResults.value.length} 条结果。`
        await refreshWorkbench(body.batch_id || '')
      } catch (err) {
        workbenchRetestFeedback.value = `页面复测失败：${err.message}`
        alert(`页面复测失败: ${err.message}`)
      } finally {
        workbenchRetesting.value = false
      }
    }

    async function refreshWorkbench(preferredBatchId = '') {
      await fetchWorkbench({ preserveRetestState: true, preferredBatchId })
      await syncRoute()
    }

    function selectRetestReport(batchId) {
      selectedRetestReportId.value = batchId
      const compareCandidates = compareCandidateReports.value
      selectedCompareReportId.value =
        (selectedCompareReportId.value && compareCandidates.find(item => item.batch_id === selectedCompareReportId.value)?.batch_id) ||
        (compareCandidates[0]?.batch_id || '')
      const report = currentRetestReport.value
      if (!report) return
      workbenchRetestResults.value = report.results || []
      workbenchRetestFeedback.value = `已切换到 ${formatDateTime(report.created_at)} 的复测报告，共 ${report.result_count} 条结果。`
    }

    function selectCompareReport(batchId) {
      selectedCompareReportId.value = batchId
    }

    async function deleteRetestResult(resultId) {
      if (!selectedJobId.value || !selectedPageUrl.value || !resultId) return
      if (!window.confirm('确定删除这条复测结果吗？')) return
      deletingRetestResultId.value = String(resultId)
      try {
        const endpoint = `${apiBase.value}/jobs/${selectedJobId.value}/pages/retest-results/${encodeURIComponent(resultId)}?url=${encodeURIComponent(selectedPageUrl.value)}`
        const res = await fetch(endpoint, { method: 'DELETE' })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || '删除复测结果失败')
        workbenchRetestFeedback.value = '复测结果已删除。'
        await refreshWorkbench(selectedRetestReportId.value)
      } catch (err) {
        alert(`删除复测结果失败: ${err.message}`)
      } finally {
        deletingRetestResultId.value = ''
      }
    }

    async function runAIExplain() {
      if (!selectedJobId.value || !selectedPageUrl.value) return
      aiExplainLoading.value = true
      aiExplainError.value = ''
      try {
        const res = await fetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/ai-explain`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: selectedPageUrl.value,
            audience: aiExplainAudience.value,
            batch_id: currentRetestReport.value?.batch_id || '',
            compare_batch_id: compareRetestReport.value?.batch_id || '',
          }),
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || 'AI解释失败')
        aiExplainResult.value = body.explanation?.content || ''
      } catch (err) {
        aiExplainError.value = err.message
      } finally {
        aiExplainLoading.value = false
      }
    }

    async function runAIMultiRoundValidation() {
      if (!selectedJobId.value || !selectedPageUrl.value) return
      aiValidateLoading.value = true
      aiValidateError.value = ''
      try {
        const res = await fetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/ai-validate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: selectedPageUrl.value,
            mode: aiValidateMode.value,
          }),
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || 'AI多轮验证失败')
        aiValidateResult.value = body
        await refreshWorkbench()
        if (body.batch_id) {
          selectedAIMultiRoundReportId.value = body.batch_id
        }
      } catch (err) {
        aiValidateError.value = err.message
      } finally {
        aiValidateLoading.value = false
      }
    }

    function selectAIMultiRoundReport(batchId) {
      selectedAIMultiRoundReportId.value = batchId
    }

    async function deleteAIMultiRoundReport(batchId) {
      if (!selectedJobId.value || !selectedPageUrl.value || !batchId) return
      if (!window.confirm('确定删除这份 AI 多轮验证记录吗？')) return
      deletingAIMultiRoundReportId.value = batchId
      try {
        const endpoint = `${apiBase.value}/jobs/${selectedJobId.value}/pages/ai-validate-reports/${encodeURIComponent(batchId)}?url=${encodeURIComponent(selectedPageUrl.value)}`
        const res = await fetch(endpoint, { method: 'DELETE' })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || '删除 AI 多轮验证记录失败')
        aiValidateError.value = ''
        aiValidateResult.value = null
        if (selectedAIMultiRoundReportId.value === batchId) {
          selectedAIMultiRoundReportId.value = ''
        }
        await refreshWorkbench()
      } catch (err) {
        aiValidateError.value = err.message
      } finally {
        deletingAIMultiRoundReportId.value = ''
      }
    }

    async function syncRoute() {
      const url = await fetchWorkbenchUrl(selectedJobId.value, selectedPageUrl.value)
      window.history.replaceState({}, '', url)
    }

    async function goHome() {
      window.location.href = '/'
    }

    async function openSelectedWorkbench() {
      if (!selectedJobId.value || !selectedPageUrl.value) return
      await fetchWorkbench()
      await syncRoute()
    }

    function readRoute() {
      const params = new URLSearchParams(window.location.search)
      return {
        jobId: (params.get('job_id') || '').trim(),
        pageUrl: (params.get('page_url') || '').trim(),
      }
    }

    watch(apiBase, value => {
      localStorage.setItem('apiBase', value)
    })

    watch(selectedJobId, async jobId => {
      selectedPageUrl.value = ''
      workbenchData.value = null
      if (!jobId) {
        pages.value = []
        return
      }
      await fetchPages(jobId)
    })

    onMounted(async () => {
      await fetchJobs()
      const route = readRoute()
      if (route.jobId) {
        selectedJobId.value = route.jobId
        await fetchPages(route.jobId)
      } else if (jobs.value.length) {
        selectedJobId.value = jobs.value[0].id
        await fetchPages(selectedJobId.value)
      }

      if (route.pageUrl) {
        selectedPageUrl.value = route.pageUrl
        await fetchWorkbench()
      } else if (pages.value.length) {
        selectedPageUrl.value = pages.value[0].url
      }
    })

    return {
      apiBase,
      jobs,
      pages,
      selectedJobId,
      selectedPageUrl,
      selectedJob,
      selectedPage,
      workbenchData,
      workbenchLoading,
      workbenchRetesting,
      workbenchRetestResults,
      workbenchRetestFeedback,
      selectedRetestReportId,
      selectedCompareReportId,
      deletingRetestResultId,
      aiExplainAudience,
      aiExplainLoading,
      aiExplainError,
      aiExplainResult,
      aiValidateMode,
      aiValidateLoading,
      aiValidateError,
      aiValidateResult,
      selectedAIMultiRoundReportId,
      deletingAIMultiRoundReportId,
      currentRetestReport,
      currentAIMultiRoundReport,
      compareCandidateReports,
      compareRetestReport,
      retestComparison,
      workbenchSelectedPreset,
      workbenchSelectedVector,
      workbenchCustomPayload,
      workbenchRetestPayloadOptions,
      formatDateTime,
      copyToClipboard,
      applySuccessfulPayload,
      applyWorkbenchRetestPreset,
      runWorkbenchRetest,
      refreshWorkbench,
      selectRetestReport,
      selectCompareReport,
      deleteRetestResult,
      runAIExplain,
      runAIMultiRoundValidation,
      selectAIMultiRoundReport,
      deleteAIMultiRoundReport,
      openSelectedWorkbench,
      goHome,
    }
  },
  template: `
    <div class="workbenchShell">
      <header class="workbenchTopbar">
        <div>
          <div class="workbenchTopTitle">页面验证工作台</div>
          <div class="workbenchTopText">先选任务，再选已爬取页面，最后进入对应页面的验证与分析视图。</div>
        </div>
        <div class="actions">
          <button class="topActionBtn topActionBtnSecondary" @click="goHome()">返回首页</button>
        </div>
      </header>

      <section class="workbenchSelectorPanel">
        <div class="workbenchSelectorGrid">
          <div class="workbenchSelectorItem">
            <label class="label">选择任务</label>
            <select class="input" v-model="selectedJobId">
              <option value="" disabled>请选择任务</option>
              <option v-for="job in jobs" :key="job.id" :value="job.id">
                {{ job.target_url }} | {{ job.id.slice(0, 8) }}
              </option>
            </select>
          </div>
          <div class="workbenchSelectorItem">
            <label class="label">选择已爬取页面</label>
            <select class="input" v-model="selectedPageUrl" :disabled="!selectedJobId || !pages.length">
              <option value="" disabled>请选择页面</option>
              <option v-for="page in pages" :key="page.id" :value="page.url">
                {{ page.url }}
              </option>
            </select>
          </div>
          <div class="workbenchSelectorAction">
            <button class="topActionBtn" :disabled="!selectedJobId || !selectedPageUrl || workbenchLoading" @click="openSelectedWorkbench()">
              {{ workbenchLoading ? '载入中...' : '进入页面工作台' }}
            </button>
          </div>
        </div>
      </section>

      <div v-if="selectedPage && !workbenchData" class="workbenchEmptyState">
        <div class="workbenchEmptyTitle">已选择页面</div>
        <div class="workbenchEmptyText mono">{{ selectedPage.url }}</div>
        <div class="workbenchEmptyHint">点击“进入页面工作台”后加载该页面的画像、复测历史和关联风险。</div>
      </div>

      <div v-if="workbenchData">${PAGE_WORKBENCH_TEMPLATE}</div>
    </div>
  `,
}).mount('#app')

