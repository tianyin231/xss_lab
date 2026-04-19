
      import { HELP_SECTIONS } from './help-content.js'
      import { AUTH_TEMPLATE } from './auth-view.js'
      import { buildExportUrl } from './export-utils.js'
      import { APP_TEMPLATE } from './app-template.js'
      const { createApp, ref, computed, onMounted, watch, nextTick } = Vue

      createApp({
        setup() {
          const defaultApiBase = window.APP_CONFIG?.apiBase || 'http://127.0.0.1:5001/api'
          const apiBase = ref(localStorage.getItem('apiBase') || defaultApiBase)
          const authToken = ref(localStorage.getItem('authToken') || '')
          const authUser = ref(null)
          const authMode = ref('login')
          const authError = ref('')
          const authLoading = ref(false)
          const authForm = ref({
            username: '',
            password: '',
            display_name: '',
            invite_code: ''
          })
          const jobs = ref([])
          const selectedJobId = ref(null)
          const logs = ref([])
          const report = ref(null)
          const aiReport = ref([])
          const creating = ref(false)
          const analyzing = ref(false)
          const retestingFinding = ref(false)
          const findingRetestResults = ref([])
          const findingPayloadSuggestions = ref([])
          const findingPayloadSuggestionsLoading = ref(false)
          const findingRetestFeedback = ref('')
          const currentView = ref('dashboard')
          const workbenchData = ref(null)
          const workbenchLoading = ref(false)
          const workbenchError = ref('')
          const workbenchRetesting = ref(false)
          const workbenchRetestResults = ref([])
          const workbenchRetestFeedback = ref('')
          const workbenchSelectedPreset = ref('__default__')
          const workbenchSelectedVector = ref('')
          const workbenchCustomPayload = ref('')
          const helpQuery = ref('')
          const helpCategory = ref('all')
          const expandedHelpIds = ref(['term_xss', 'workflow_scan', 'result_confidence'])
          const selectedRetestPreset = ref('__default__')
          const selectedRetestVector = ref('')
          const customRetestPayload = ref('')
          
          // 布局状态
          const sidebarWidth = ref(parseInt(localStorage.getItem('sidebarWidth') || '320'))
          const logsWidth = ref(parseInt(localStorage.getItem('logsWidth') || '300'))
          const detailWidth = ref(400)
          const isResizingSidebar = ref(false)
          const isResizingLogs = ref(false)
          const isResizingDetail = ref(false)
          const isDetailView = ref(false) // 控制是否显示详细视图
          const selectedFinding = ref(null) // 选中的风险点
          const selectedPage = ref(null) // 选中的页面
          const selectedAiReport = ref(null) // 选中的AI报告
          const selectedVerification = ref(null) // 选中的动态验证结果

          // 展开与模态框状态
          const activeModal = ref(null) // { type: 'finding' | 'page', data: any }

          const form = ref({
            target_url: '',
            max_depth: 2,
            max_pages: 200,
            use_selenium: false
          })

          let es = null
          let reportTimer = null

          function buildWorkbenchUrl(jobId, pageUrl) {
            const params = new URLSearchParams(window.location.search)
            params.set('view', 'workbench')
            params.set('job_id', jobId)
            params.set('page_url', pageUrl)
            return `${window.location.pathname}?${params.toString()}`
          }

          function buildDashboardUrl() {
            const params = new URLSearchParams(window.location.search)
            params.delete('view')
            params.delete('job_id')
            params.delete('page_url')
            const query = params.toString()
            return query ? `${window.location.pathname}?${query}` : window.location.pathname
          }

          function syncWorkbenchRoute(jobId, pageUrl) {
            window.history.replaceState({}, '', buildWorkbenchUrl(jobId, pageUrl))
          }

          function syncDashboardRoute() {
            window.history.replaceState({}, '', buildDashboardUrl())
          }

          function readWorkbenchRoute() {
            const params = new URLSearchParams(window.location.search)
            const view = (params.get('view') || '').trim()
            const jobId = (params.get('job_id') || '').trim()
            const pageUrl = (params.get('page_url') || '').trim()
            if (view !== 'workbench' || !jobId || !pageUrl) return null
            return { jobId, pageUrl }
          }

          const selectedJob = computed(() => jobs.value.find(j => j.id === selectedJobId.value) || null)
          const selectedPageFindings = computed(() => {
            if (!selectedPage.value?.url || !report.value?.findings?.length) return []
            return report.value.findings.filter(finding =>
              (finding.instances || []).some(item => item.url === selectedPage.value.url)
            )
          })
          const selectedPageHighlightedHtml = computed(() => {
            if (!selectedPage.value?.content || !selectedPageFindings.value.length) return ''
            const mergedFinding = {
              instances: selectedPageFindings.value.flatMap(finding =>
                (finding.instances || []).filter(item => item.url === selectedPage.value.url)
              )
            }
            return buildHighlightedSource(selectedPage.value.content, mergedFinding, selectedPage.value.url)
          })
          const retestPayloadOptions = computed(() => {
            const options = [
              { value: '__default__', label: '系统默认 Payload', payload: '', vector: '' },
            ]
            for (const item of findingPayloadSuggestions.value || []) {
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
          const workbenchRetestPayloadOptions = computed(() => {
            const options = [
              { value: '__default__', label: '系统默认 Payload', payload: '', vector: '' },
            ]
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
          const helpSections = ref(HELP_SECTIONS)
          const helpCategories = computed(() => [
            { value: 'all', label: '全部' },
            ...helpSections.value.map(section => ({ value: section.key, label: section.label })),
          ])
          const helpEntryCount = computed(() => helpSections.value.reduce((sum, section) => sum + section.items.length, 0))
          const helpCategoryLabel = computed(() => {
            return helpCategories.value.find(item => item.value === helpCategory.value)?.label || '全部'
          })
          const filteredHelpSections = computed(() => {
            const keyword = helpQuery.value.trim().toLowerCase()
            return helpSections.value
              .filter(section => helpCategory.value === 'all' || section.key === helpCategory.value)
              .map(section => {
                const items = section.items.filter(item => {
                  if (!keyword) return true
                  const haystack = [item.q, item.a, ...(item.tags || [])].join(' ').toLowerCase()
                  return haystack.includes(keyword)
                })
                return { ...section, items }
              })
              .filter(section => section.items.length > 0)
          })

          const isAuthenticated = computed(() => Boolean(authUser.value && authToken.value))

          async function apiFetch(url, options = {}) {
            const headers = new Headers(options.headers || {})
            if (authToken.value) {
              headers.set('Authorization', `Bearer ${authToken.value}`)
            }
            const response = await fetch(url, { ...options, headers })
            if (response.status === 401 && authToken.value) {
              authToken.value = ''
              authUser.value = null
              jobs.value = []
              selectedJobId.value = null
              logs.value = []
              report.value = null
              aiReport.value = []
            }
            return response
          }

          async function fetchMe() {
            if (!authToken.value) {
              authUser.value = null
              return
            }
            const res = await apiFetch(`${apiBase.value}/auth/me`)
            const body = await res.json()
            if (!body.authenticated) {
              authToken.value = ''
              authUser.value = null
              return
            }
            authUser.value = body.user || null
          }

          function toggleAuthMode() {
            authMode.value = authMode.value === 'login' ? 'register' : 'login'
            authError.value = ''
          }

          async function submitAuth() {
            authLoading.value = true
            authError.value = ''
            try {
              const endpoint = authMode.value === 'login' ? '/auth/login' : '/auth/register'
              const res = await fetch(`${apiBase.value}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(authForm.value)
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '认证失败')
              authToken.value = body.token || ''
              authUser.value = body.user || null
              authForm.value.password = ''
              await fetchJobs()
              if (selectedJobId.value) {
                await fetchReport(selectedJobId.value)
                await fetchAIReport(selectedJobId.value)
              }
            } catch (err) {
              authError.value = err.message
            } finally {
              authLoading.value = false
            }
          }

          async function logout() {
            try {
              await apiFetch(`${apiBase.value}/auth/logout`, { method: 'POST' })
            } catch (_) {}
            authToken.value = ''
            authUser.value = null
            jobs.value = []
            selectedJobId.value = null
            logs.value = []
            report.value = null
            aiReport.value = []
            currentView.value = 'dashboard'
          }

          function formatDateTime(value) {
            if (value === null || value === undefined || value === '') return '-'
            const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
            if (Number.isNaN(date.getTime())) return '-'
            const formatter = new Intl.DateTimeFormat('zh-CN', {
              timeZone: 'Asia/Shanghai',
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: false
            })
            const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]))
            return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
          }

          function escapeHtml(value) {
            return String(value)
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;')
          }

          function buildHighlightedSource(content, finding, pageUrl) {
            const lines = String(content || '').split('\n')
            const hitLines = new Set(
              (finding.instances || [])
                .filter(item => !item.url || item.url === pageUrl)
                .map(item => Number(item.line))
                .filter(line => Number.isFinite(line) && line > 0)
            )
            return lines
              .map((line, index) => {
                const lineNo = index + 1
                const cls = hitLines.has(lineNo) ? 'source-line source-line-hit' : 'source-line'
                return (
                  '<div class="' + cls + '">' +
                    '<span class="source-line-no">' + lineNo + '</span>' +
                    '<span class="source-line-text">' + escapeHtml(line) + '</span>' +
                  '</div>'
                )
              })
              .join('')
          }

          async function fetchJobs() {
            const res = await apiFetch(`${apiBase.value}/jobs`)
            jobs.value = await res.json()
            if (!selectedJobId.value && jobs.value.length) selectedJobId.value = jobs.value[0].id
          }

          async function fetchReport(jobId) {
            if (!jobId) return
            const res = await apiFetch(`${apiBase.value}/jobs/${jobId}/report`)
            const data = await res.json()
            report.value = data
            if (selectedFinding.value && data.findings?.length) {
              const matchedFinding = data.findings.find(item =>
                item.kind === selectedFinding.value.kind && item.title === selectedFinding.value.title
              )
              if (matchedFinding) selectedFinding.value = matchedFinding
            }
            // 从数据库加载历史日志
            logs.value = (data.logs || []).map(l => ({ ts: l.ts, message: l.message }))
            
            // 自动滚动到底部
            nextTick(() => {
              const logContainer = document.querySelector('.log')
              if (logContainer) logContainer.scrollTop = logContainer.scrollHeight
            })
          }

          function triggerReportUpdate(jobId) {
            if (reportTimer) return
            reportTimer = setTimeout(async () => {
              await fetchReport(jobId)
              reportTimer = null
            }, 1000)
          }

          function attachEvents(jobId) {
            if (es) es.close()
            if (reportTimer) {
              clearTimeout(reportTimer)
              reportTimer = null
            }
            es = new EventSource(`${apiBase.value}/jobs/${jobId}/events`)
            es.addEventListener('log', (ev) => {
              const msg = JSON.parse(ev.data)
              const newLog = { ts: msg.ts, message: msg.data?.message || '' }
              logs.value.push(newLog)
              if (logs.value.length > 2000) logs.value.splice(0, logs.value.length - 2000)
              
              nextTick(() => {
                const logContainer = document.querySelector('.log')
                if (logContainer) logContainer.scrollTop = logContainer.scrollHeight
              })
            })
            es.addEventListener('job', async () => {
              await fetchJobs()
              triggerReportUpdate(jobId)
            })
            es.addEventListener('page', () => {
              triggerReportUpdate(jobId)
            })
            es.addEventListener('finding', () => {
              triggerReportUpdate(jobId)
            })
            es.addEventListener('error', async (ev) => {
              const msg = JSON.parse(ev.data)
              logs.value.push({ ts: msg.ts, message: `ERROR: ${msg.data?.message || ''}` })
              await fetchJobs()
              triggerReportUpdate(jobId)
            })
          }

          async function createJob() {
            if (!form.value.target_url) {
              alert('请输入目标网址')
              return
            }
            creating.value = true
            try {
              const res = await apiFetch(`${apiBase.value}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form.value)
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '创建失败')
              await fetchJobs()
              selectedJobId.value = body.job_id
              await fetchReport(body.job_id)
              attachEvents(body.job_id)
            } catch (err) {
              alert(`扫描启动失败: ${err.message}`)
            } finally {
              creating.value = false
            }
          }

          async function stopJob(jobId) {
            await apiFetch(`${apiBase.value}/jobs/${jobId}/stop`, { method: 'POST' })
            await fetchJobs()
            await fetchReport(jobId)
          }

          async function deleteJob(jobId) {
            if (!confirm('确定要彻底删除该任务及其所有扫描结果吗？此操作不可恢复。')) return
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${jobId}`, { method: 'DELETE' })
              if (!res.ok) throw new Error('删除失败')
              if (selectedJobId.value === jobId) {
                selectedJobId.value = null
                report.value = null
                aiReport.value = null
                logs.value = []
              }
              await fetchJobs()
            } catch (err) {
              alert(err.message)
            }
          }

          async function analyzeJob(jobId) {
            if (!jobId) return
            analyzing.value = true
            try {
              // 添加开始分析日志
              const startTime = Date.now()
              logs.value.push({ ts: startTime / 1000, message: `[AI分析] 开始分析任务 ${jobId}` })
              
              const res = await apiFetch(`${apiBase.value}/jobs/${jobId}/analyze`, { method: 'POST' })
              
              if (!res.ok) {
                const error = await res.json()
                throw new Error(error.error || '分析失败')
              }
              
              // 添加分析完成日志
              const endTime = Date.now()
              logs.value.push({ ts: endTime / 1000, message: `[AI分析] 分析完成，耗时 ${(endTime - startTime) / 1000} 秒` })
              
              await fetchAIReport(jobId)
              
              // 添加报告获取日志
              logs.value.push({ ts: Date.now() / 1000, message: `[AI分析] 已获取AI报告` })
              
              alert('AI分析完成')
            } catch (err) {
              // 添加错误日志
              logs.value.push({ ts: Date.now() / 1000, message: `[AI分析] 分析失败: ${err.message}` })
              alert(`分析失败: ${err.message}`)
            } finally {
              analyzing.value = false
            }
          }

          async function fetchAIReport(jobId) {
            if (!jobId) return
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${jobId}/ai-report`)
              aiReport.value = await res.json()
            } catch (err) {
              console.error('获取AI报告失败:', err)
              aiReport.value = []
            }
          }

          function exportReport(format = 'html') {
            if (!selectedJob.value?.id) return
            window.location.href = buildExportUrl(apiBase.value, selectedJob.value.id, format)
          }

          function startResizeSidebar(e) {
            isResizingSidebar.value = true
            document.addEventListener('mousemove', handleResize)
            document.addEventListener('mouseup', stopResize)
          }

          function startResizeLogs(e) {
            isResizingLogs.value = true
            document.addEventListener('mousemove', handleResize)
            document.addEventListener('mouseup', stopResize)
          }

          function handleResize(e) {
            if (isResizingSidebar.value) {
              sidebarWidth.value = e.clientX
            } else if (isResizingLogs.value) {
              const rect = document.querySelector('.main').getBoundingClientRect()
              logsWidth.value = e.clientX - rect.left
            }
          }

          function stopResize() {
            if (isResizingSidebar.value) localStorage.setItem('sidebarWidth', sidebarWidth.value)
            if (isResizingLogs.value) localStorage.setItem('logsWidth', logsWidth.value)
            isResizingSidebar.value = false
            isResizingLogs.value = false
            document.removeEventListener('mousemove', handleResize)
            document.removeEventListener('mouseup', stopResize)
          }

          async function fetchPageDetail(pageId) {
            const res = await apiFetch(`${apiBase.value}/pages/${pageId}`)
            if (!res.ok) throw new Error('获取页面详情失败')
            return await res.json()
          }

          async function fetchPageWorkbench(url) {
            if (!selectedJobId.value || !url) throw new Error('缺少页面地址')
            const endpoint = `${apiBase.value}/jobs/${selectedJobId.value}/pages/workbench?url=${encodeURIComponent(url)}`
            const res = await apiFetch(endpoint)
            const body = await res.json()
            if (!res.ok) throw new Error(body.error || '获取页面工作台失败')
            return body
          }

          async function fetchWorkbenchUrl(jobId = '', pageUrl = '') {
            const params = new URLSearchParams()
            if (jobId) params.set('job_id', jobId)
            if (pageUrl) params.set('page_url', pageUrl)
            const suffix = params.toString() ? `?${params.toString()}` : ''
            const res = await apiFetch(`${apiBase.value}/workbench/url${suffix}`)
            const body = await res.json()
            if (!res.ok) throw new Error(body.error || '获取工作台地址失败')
            return body.url
          }

          function resetWorkbenchRetestState() {
            workbenchRetestResults.value = []
            workbenchRetestFeedback.value = ''
            workbenchSelectedPreset.value = '__default__'
            workbenchSelectedVector.value = ''
            workbenchCustomPayload.value = ''
          }

          async function openWorkbenchHome() {
            try {
              const url = await fetchWorkbenchUrl()
              window.location.href = url
            } catch (err) {
              alert(`打开工作台失败: ${err.message}`)
            }
          }

          async function openPageWorkbench(page) {
            const pageUrl = typeof page === 'string' ? page : page?.url
            if (!pageUrl) return
            workbenchLoading.value = true
            workbenchError.value = ''
            try {
              if (!selectedJobId.value) {
                throw new Error('缺少任务上下文')
              }
              workbenchData.value = await fetchPageWorkbench(pageUrl)
              closeModal()
              currentView.value = 'page-workbench'
              syncWorkbenchRoute(selectedJobId.value, pageUrl)
              resetWorkbenchRetestState()
            } catch (err) {
              workbenchError.value = err.message
              alert(`打开页面工作台失败: ${err.message}`)
            } finally {
              workbenchLoading.value = false
            }
          }

          async function openPageWorkbenchRedirect(page) {
            const pageUrl = typeof page === 'string' ? page : page?.url
            if (!selectedJobId.value) {
              alert('请先选择任务')
              return
            }
            if (!pageUrl) return
            try {
              const url = await fetchWorkbenchUrl(selectedJobId.value, pageUrl)
              window.location.href = url
            } catch (err) {
              alert(`打开页面工作台失败: ${err.message}`)
            }
          }

          async function refreshWorkbench() {
            if (!workbenchData.value?.page?.url) return
            workbenchLoading.value = true
            workbenchError.value = ''
            try {
              workbenchData.value = await fetchPageWorkbench(workbenchData.value.page.url)
              if (selectedJobId.value) {
                syncWorkbenchRoute(selectedJobId.value, workbenchData.value.page.url)
              }
            } catch (err) {
              workbenchError.value = err.message
              alert(`刷新页面工作台失败: ${err.message}`)
            } finally {
              workbenchLoading.value = false
            }
          }

          function closeWorkbench() {
            currentView.value = 'dashboard'
            syncDashboardRoute()
          }


          function closeModal() {
            activeModal.value = null
          }

          function toggleDetailView() {
            isDetailView.value = !isDetailView.value
            if (!isDetailView.value) {
              selectedFinding.value = null
              selectedPage.value = null
              selectedAiReport.value = null
              selectedVerification.value = null
            }
          }

          async function selectFinding(finding) {
            selectedFinding.value = finding
            selectedPage.value = null
            selectedAiReport.value = null
            selectedVerification.value = null
            findingRetestResults.value = []
            findingPayloadSuggestions.value = []
            findingRetestFeedback.value = ''
            selectedRetestPreset.value = '__default__'
            selectedRetestVector.value = ''
            customRetestPayload.value = ''
          }

          async function updateFindingStatus(status) {
            if (!selectedJobId.value || !selectedFinding.value) return
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${selectedJobId.value}/finding-status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  kind: selectedFinding.value.kind,
                  title: selectedFinding.value.title,
                  status
                })
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '状态更新失败')
              await fetchReport(selectedJobId.value)
            } catch (err) {
              alert(`状态更新失败: ${err.message}`)
            }
          }


          async function fetchFindingPayloadSuggestions() {
            if (!selectedJobId.value || !selectedPage.value) return
            findingPayloadSuggestionsLoading.value = true
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/payloads`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  url: selectedPage.value.url || ''
                })
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '获取推荐 payload 失败')
              findingPayloadSuggestions.value = body.payloads || []
            } catch (err) {
              console.error('获取推荐 payload 失败:', err)
              findingPayloadSuggestions.value = []
            } finally {
              findingPayloadSuggestionsLoading.value = false
            }
          }

          function applyRetestPreset() {
            const option = retestPayloadOptions.value.find(item => item.value === selectedRetestPreset.value)
            if (!option) return
            if (selectedRetestPreset.value !== '__custom__') {
              customRetestPayload.value = ''
            }
            if (!selectedRetestVector.value && option.vector) {
              selectedRetestVector.value = option.vector
            }
          }

          function openModal(type, data) {
            activeModal.value = { type, data }
          }

          function toggleHelpView() {
            currentView.value = currentView.value === 'help' ? 'dashboard' : 'help'
            closeModal()
          }

          function toggleHelpItem(itemId) {
            const current = new Set(expandedHelpIds.value)
            if (current.has(itemId)) {
              current.delete(itemId)
            } else {
              current.add(itemId)
            }
            expandedHelpIds.value = [...current]
          }

          function isHelpItemExpanded(itemId) {
            return expandedHelpIds.value.includes(itemId)
          }

          async function retestSelectedFinding(payloadOverride = '', vectorOverride = '') {
            if (!selectedJobId.value || !selectedPage.value) return

            retestingFinding.value = true
            findingRetestFeedback.value = '正在执行单点复测...'
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/retest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  url: selectedPage.value.url || '',
                  payload: payloadOverride,
                  vector: vectorOverride
                })
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '单点复测失败')

              findingRetestResults.value = body.results || []
              findingRetestFeedback.value = `单点复测完成，已生成 ${findingRetestResults.value.length} 条结果。`
              logs.value.push({
                ts: Date.now() / 1000,
                message: `[页面复测] ${selectedPage.value.url} -> ${findingRetestResults.value.length} 条结果`
              })
            } catch (err) {
              findingRetestFeedback.value = `单点复测失败：${err.message}`
              alert(`单点复测失败: ${err.message}`)
            } finally {
              retestingFinding.value = false
            }
          }

          async function runRetestFromControls() {
            let payload = ''
            let vector = selectedRetestVector.value || ''
            const option = retestPayloadOptions.value.find(item => item.value === selectedRetestPreset.value)
            if (selectedRetestPreset.value === '__custom__') {
              payload = customRetestPayload.value.trim()
            } else if (option) {
              payload = option.payload || ''
              if (!vector && option.vector) {
                vector = option.vector
              }
            }
            await retestSelectedFinding(payload, vector)
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

          async function runWorkbenchRetest() {
            if (!selectedJobId.value || !workbenchData.value?.page?.url) return

            let payload = ''
            let vector = workbenchSelectedVector.value || ''
            const option = workbenchRetestPayloadOptions.value.find(item => item.value === workbenchSelectedPreset.value)
            if (workbenchSelectedPreset.value === '__custom__') {
              payload = workbenchCustomPayload.value.trim()
            } else if (option) {
              payload = option.payload || ''
              if (!vector && option.vector) {
                vector = option.vector
              }
            }

            workbenchRetesting.value = true
            workbenchRetestFeedback.value = '正在执行页面复测...'
            try {
              const res = await apiFetch(`${apiBase.value}/jobs/${selectedJobId.value}/pages/retest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  url: workbenchData.value.page.url,
                  payload,
                  vector,
                })
              })
              const body = await res.json()
              if (!res.ok) throw new Error(body.error || '页面复测失败')
              workbenchRetestResults.value = body.results || []
              workbenchRetestFeedback.value = `页面复测完成，已生成 ${workbenchRetestResults.value.length} 条结果。`
              logs.value.push({
                ts: Date.now() / 1000,
                message: `[页面工作台] ${workbenchData.value.page.url} -> ${workbenchRetestResults.value.length} 条复测结果`
              })
              await refreshWorkbench()
            } catch (err) {
              workbenchRetestFeedback.value = `页面复测失败：${err.message}`
              alert(`页面复测失败: ${err.message}`)
            } finally {
              workbenchRetesting.value = false
            }
          }

          async function selectPage(page) {
            try {
              const pageDetail = page.id ? await fetchPageDetail(page.id) : page
              selectedPage.value = { ...page, ...pageDetail }
            } catch (err) {
              console.error('获取页面详情失败:', err)
              selectedPage.value = page
            }
            selectedFinding.value = null
            selectedAiReport.value = null
            selectedVerification.value = null
            findingRetestResults.value = []
            findingPayloadSuggestions.value = []
            findingRetestFeedback.value = ''
            selectedRetestPreset.value = '__default__'
            selectedRetestVector.value = ''
            customRetestPayload.value = ''
            fetchFindingPayloadSuggestions()
          }

          function selectAiReport(item) {
            selectedAiReport.value = item
            selectedFinding.value = null
            selectedPage.value = null
            selectedVerification.value = null
          }

          function selectVerification(item) {
            selectedVerification.value = item
            selectedFinding.value = null
            selectedPage.value = null
            selectedAiReport.value = null
          }

          function startResizeDetail(e) {
            isResizingDetail.value = true
            document.addEventListener('mousemove', handleResize)
            document.addEventListener('mouseup', stopResize)
          }

          function handleResize(e) {
            if (isResizingSidebar.value) {
              sidebarWidth.value = e.clientX
            } else if (isResizingLogs.value) {
              const rect = document.querySelector('.main').getBoundingClientRect()
              logsWidth.value = e.clientX - rect.left
            } else if (isResizingDetail.value) {
              const rect = document.querySelector('.main').getBoundingClientRect()
              detailWidth.value = rect.right - e.clientX
            }
          }

          function stopResize() {
            if (isResizingSidebar.value) localStorage.setItem('sidebarWidth', sidebarWidth.value)
            if (isResizingLogs.value) localStorage.setItem('logsWidth', logsWidth.value)
            isResizingSidebar.value = false
            isResizingLogs.value = false
            isResizingDetail.value = false
            document.removeEventListener('mousemove', handleResize)
            document.removeEventListener('mouseup', stopResize)
          }

          onMounted(async () => {
            await fetchMe()
            if (isAuthenticated.value) {
              await fetchJobs()
              if (selectedJobId.value) {
                await fetchReport(selectedJobId.value)
                attachEvents(selectedJobId.value)
              }
            }
            
            // 按 ESC 关闭模态框
            window.addEventListener('keydown', (e) => {
              if (e.key === 'Escape') closeModal()
            })
          })

          watch(apiBase, (v) => {
            localStorage.setItem('apiBase', v)
          })

          watch(authToken, (v) => {
            if (v) localStorage.setItem('authToken', v)
            else localStorage.removeItem('authToken')
          })

          watch(selectedJobId, async (jobId) => {
            if (!isAuthenticated.value) return
            if (!jobId) return
            closeModal()
            await fetchJobs()
            await fetchReport(jobId)
            await fetchAIReport(jobId)
            selectedFinding.value = null
            selectedPage.value = null
            selectedAiReport.value = null
            selectedVerification.value = null
            findingRetestResults.value = []
            findingPayloadSuggestions.value = []
            findingPayloadSuggestionsLoading.value = false
            findingRetestFeedback.value = ''
            selectedRetestPreset.value = '__default__'
            selectedRetestVector.value = ''
            customRetestPayload.value = ''
            workbenchData.value = null
            workbenchError.value = ''
            resetWorkbenchRetestState()
            if (currentView.value !== 'help') currentView.value = 'dashboard'
            attachEvents(jobId)
          })

          return {
            apiBase, authUser, authMode, authError, authLoading, authForm, isAuthenticated, submitAuth, toggleAuthMode, logout,
            jobs, selectedJobId, selectedJob, logs, report, aiReport, form, creating, analyzing,
            currentView, helpQuery, helpCategory, helpCategories, filteredHelpSections, helpSections, helpEntryCount, helpCategoryLabel,
            workbenchData, workbenchLoading, workbenchError, workbenchRetesting, workbenchRetestResults, workbenchRetestFeedback,
            workbenchSelectedPreset, workbenchSelectedVector, workbenchCustomPayload, workbenchRetestPayloadOptions,
            sidebarWidth, logsWidth, detailWidth, isResizingSidebar, isResizingLogs, isResizingDetail, isDetailView, selectedFinding, selectedPage, selectedAiReport, selectedVerification,
            retestingFinding, findingRetestResults, findingPayloadSuggestions, findingPayloadSuggestionsLoading, findingRetestFeedback,
            selectedRetestPreset, selectedRetestVector, customRetestPayload, retestPayloadOptions,
            activeModal,
            formatDateTime, selectedPageFindings, selectedPageHighlightedHtml,
            fetchJobs, fetchReport, createJob, stopJob, deleteJob, analyzeJob, fetchAIReport, exportReport,
            startResizeSidebar, startResizeLogs, startResizeDetail, openModal, closeModal, toggleDetailView, selectFinding, selectPage, selectAiReport, selectVerification, updateFindingStatus, retestSelectedFinding, runRetestFromControls, applyRetestPreset, toggleHelpView, toggleHelpItem, isHelpItemExpanded,
            openWorkbenchHome, openPageWorkbenchRedirect,
            openPageWorkbench, closeWorkbench, refreshWorkbench, runWorkbenchRetest, applyWorkbenchRetestPreset
          }
        },
        template: `
          <div v-if="isAuthenticated">
            <div class="authFloatingBar">
              <span class="authFloatingUser">{{ authUser.display_name || authUser.username }}</span>
              <button class="topActionBtn topActionBtnSecondary" @click="logout()">退出</button>
            </div>
            ${APP_TEMPLATE}
          </div>
          <div v-else>${AUTH_TEMPLATE}</div>
        `
      }).mount('#app')
    