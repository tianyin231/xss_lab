import { HELP_VIEW_TEMPLATE } from './help-view.js'

export const APP_TEMPLATE = `
          <div class="layout" :class="{ 'layout-help': currentView === 'help' }">
            <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
              <div class="sidebar-content">
                <div class="brand">
                  <div class="title">XSSLab</div>
                  <div class="sub">任务与报告</div>
                </div>

                <div class="card">
                  <div class="cardTitle">API</div>
                  <input class="input" v-model="apiBase" placeholder="http://127.0.0.1:5001/api" />
                </div>

                <div class="card">
                  <div class="cardTitle">新建任务</div>
                  <label class="label">目标网址</label>
                  <input class="input" v-model="form.target_url" placeholder="https://example.com/" />
                  <div class="row">
                    <div class="col">
                      <label class="label">深度</label>
                      <input class="input" v-model.number="form.max_depth" type="number" min="0" max="10" />
                    </div>
                    <div class="col">
                      <label class="label">页数</label>
                      <input class="input" v-model.number="form.max_pages" type="number" min="1" max="20000" />
                    </div>
                  </div>
                  <label class="check">
                    <input type="checkbox" v-model="form.use_selenium" />
                    <span>使用 Selenium（可选）</span>
                  </label>
                  <button class="btn" :disabled="creating" @click="createJob">
                    {{ creating ? '创建中…' : '开始扫描' }}
                  </button>
                </div>

                <div class="card">
                  <div class="cardTitle">任务列表</div>
                  <div class="jobList">
                    <div
                      v-for="j in jobs"
                      :key="j.id"
                      class="job"
                      :class="{ active: j.id === selectedJobId }"
                      @click="selectedJobId = j.id"
                    >
                      <div class="jobHeader">
                        <div class="jobUrl">{{ j.target_url }}</div>
                        <button class="jobDeleteBtn" title="删除任务" @click.stop="deleteJob(j.id)">
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6"/>
                          </svg>
                        </button>
                      </div>
                      <div class="jobMeta">
                        <span class="pill">{{ j.status }}</span>
                        <span class="mono">{{ j.id.slice(0, 8) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <div class="resizer-v" :class="{ active: isResizingSidebar }" @mousedown="startResizeSidebar"></div>

    <main class="main" :class="{ 'main-help': currentView === 'help' }">
      <div class="topbar" :class="{ 'topbar-help': currentView === 'help' }">
                <div>
                  <div class="h1">{{ currentView === 'help' ? '帮助 / 知识库' : '实时任务' }}</div>
                  <div class="muted" v-if="currentView === 'help'">解释系统中的名词、原理、结果和常见问题</div>
                  <div class="muted" v-else-if="selectedJob">{{ selectedJob.target_url }}</div>
                </div>
                <div class="actions" v-if="currentView !== 'help' && selectedJob">
                  <button class="topActionBtn" v-if="selectedJob.status === 'running'" @click="stopJob(selectedJob.id)">停止</button>
                  <button class="topActionBtn" @click="toggleDetailView">
                    {{ isDetailView ? '返回' : '详细视图' }}
                  </button>
                  <button class="topActionBtn" @click="async () => { await fetchJobs(); await fetchReport(selectedJob.id); }">刷新报告</button>
                  <button class="topActionBtn" :disabled="analyzing" @click="analyzeJob(selectedJob.id)">
                    {{ analyzing ? '分析中...' : 'AI分析' }}
                  </button>
                  <button class="topActionBtn" @click="exportReport('html')">导出报告</button>
                  <button class="topActionBtn topActionBtnSecondary" @click="toggleHelpView()">帮助</button>
                </div>
                <div class="actions" v-else-if="currentView === 'help'">
                  <button class="topActionBtn topActionBtnSecondary" @click="toggleHelpView()">返回任务</button>
                </div>
              </div>

              <div v-if="currentView === 'help'">${HELP_VIEW_TEMPLATE}</div>

              <div v-else class="grid" :class="{ 'detail-view': isDetailView }">
                <!-- 实时日志 -->
                <section class="panel" :style="{ width: logsWidth + 'px' }">
                  <div class="panelTitle">实时日志</div>
                  <div class="log">
                    <div class="logLine" v-for="(l, idx) in logs" :key="idx">
                      <span class="mono">{{ formatDateTime(l.ts) }}</span>
                      <span class="logMsg">{{ l.message }}</span>
                    </div>
                  </div>
                </section>

                <div class="resizer-v" :class="{ active: isResizingLogs }" @mousedown="startResizeLogs"></div>

                <!-- 扫描报告 -->
                <section class="panel" style="flex: 1">
                  <div class="panel-header">
                    <div class="panelTitle">扫描报告</div>
                  </div>
                  <div v-if="!report" class="muted" style="padding: 20px">暂无</div>
                  <div v-else class="report">
                    <!-- 扫描概览 -->
                    <div class="section">
                      <div class="sectionTitle">扫描概览</div>
                      <div class="kpis">
                        <div class="kpi">
                          <div class="kpiLabel">页面</div>
                          <div class="kpiValue">{{ report.stats.pages }}</div>
                        </div>
                        <div class="kpi">
                          <div class="kpiLabel">发现</div>
                          <div class="kpiValue">{{ report.stats.findings }}</div>
                        </div>
                        <div class="kpi">
                          <div class="kpiLabel">状态</div>
                          <div class="kpiValue">{{ report.job.status }}</div>
                        </div>
                      </div>
                    </div>

                    <!-- 发现列表 -->
                    <div class="section">
                      <div class="sectionTitle">发现列表</div>
                      <div class="tableWrap">
                        <table class="table">
                          <thead>
                            <tr>
                              <th style="width: 80px">级别</th>
                              <th style="width: 110px">最终判断</th>
                              <th style="width: 96px">状态</th>
                              <th style="width: 120px">类型</th>
                              <th>标题</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(f, idx) in report.findings" :key="idx" class="clickable" :class="{ 'selected': selectedFinding && selectedFinding.title === f.title }" @click="isDetailView ? selectFinding(f) : openModal('finding', f)">
                              <td><span class="pill" :class="'sev_' + f.severity">{{ f.severity_label || f.severity }}</span></td>
                              <td><span class="pill" :class="'assessment_' + f.final_assessment">{{ f.final_assessment_label || f.final_assessment }}</span></td>
                              <td><span class="pill review-pill">{{ f.review_status_label || f.review_status }}</span></td>
                              <td class="mono">{{ f.kind_display || f.kind }}</td>
                              <td>{{ f.title }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <!-- 已爬取页面 -->
                    <div class="section">
                      <div class="sectionTitle">已爬取页面（最近 100）</div>
                      <div class="tableWrap">
                        <table class="table">
                          <thead>
                            <tr>
                              <th style="width: 60px">状态</th>
                              <th style="width: 120px">类型</th>
                              <th>URL</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(p, idx) in report.pages.slice(-100)" :key="idx" class="clickable" :class="{ 'selected': selectedPage && selectedPage.url === p.url }" @click="isDetailView ? selectPage(p) : openModal('page', p)">
                              <td class="mono">{{ p.status_code }}</td>
                              <td class="mono">{{ p.content_type }}</td>
                              <td class="mono">{{ p.url }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <!-- AI分析报告 -->
                    <div v-if="aiReport && aiReport.length > 0" class="section">
                      <div class="sectionTitle">AI分析报告</div>
                      <div class="tableWrap">
                        <table class="table">
                          <thead>
                            <tr>
                              <th style="width: 220px">页面</th>
                              <th>摘要</th>
                              <th style="width: 170px">时间</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="(r, idx) in aiReport"
                              :key="idx"
                              class="clickable"
                              :class="{ selected: selectedAiReport && selectedAiReport.id === r.id }"
                              @click="isDetailView ? selectAiReport(r) : openModal('ai', r)"
                            >
                              <td class="mono">{{ r.page_url }}</td>
                              <td>{{ r.summary }}</td>
                              <td class="mono">{{ formatDateTime(r.created_at) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div v-if="report.dynamic_verification && report.dynamic_verification.results && report.dynamic_verification.results.length > 0" class="section">
                      <div class="sectionTitle">动态验证结果</div>
                      <div class="tableWrap">
                        <table class="table">
                          <thead>
                            <tr>
                              <th style="width: 90px">等级</th>
                              <th style="width: 90px">向量</th>
                              <th style="width: 140px">参数</th>
                              <th>摘要</th>
                              <th style="width: 170px">时间</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="(item, idx) in report.dynamic_verification.results"
                              :key="'verify-' + idx"
                              class="clickable"
                              :class="{ selected: selectedVerification && selectedVerification.id === item.id }"
                              @click="isDetailView ? selectVerification(item) : openModal('verification', item)"
                            >
                              <td>
                                <span class="pill" :class="'sev_' + (item.level === 'confirmed' ? 'high' : item.level === 'suspected' ? 'medium' : 'low')">
                                  {{ item.level_label || item.level }}
                                </span>
                              </td>
                              <td class="mono">{{ item.vector }}</td>
                              <td class="mono">{{ item.parameter_name || '-' }}</td>
                              <td>{{ item.summary }}</td>
                              <td class="mono">{{ formatDateTime(item.created_at) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </section>

                <!-- 详细信息（仅在详细视图中显示） -->
                <div v-if="isDetailView" class="resizer-v" :class="{ active: isResizingDetail }" @mousedown="startResizeDetail"></div>
                <section v-if="isDetailView" class="panel" :style="{ width: detailWidth + 'px' }">
                  <div class="panelTitle">详细信息</div>
                  <div class="report">
                    <!-- 风险点详细信息 -->
                    <div v-if="selectedFinding" class="section">
                      <div class="sectionTitle">风险点详情</div>
                      <div class="modal-section">
                        <div class="modal-label">漏洞标题</div>
                        <div class="modal-value" style="font-weight: 700; font-size: 16px;">{{ selectedFinding.title }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">危险等级</div>
                        <div class="modal-value">
                          <span class="pill" :class="'sev_' + selectedFinding.severity">{{ selectedFinding.severity_label || selectedFinding.severity }}</span>
                        </div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.linked_verification_results && selectedFinding.linked_verification_results.length">
                        <div class="modal-label">关联动态验证</div>
                        <div class="instance-list">
                          <div class="instance-item" v-for="(verification, vidx) in selectedFinding.linked_verification_results" :key="'linked-verification-' + vidx">
                            <div class="instance-meta">
                              <span>{{ verification.level_label || verification.level }}</span>
                              <span>{{ verification.vector }}</span>
                              <span v-if="verification.parameter_name">{{ verification.parameter_name }}</span>
                            </div>
                            <div class="ast-flow-line"><strong>目标：</strong>{{ verification.target_url }}</div>
                            <div class="ast-flow-line"><strong>结论：</strong>{{ verification.summary }}</div>
                            <div class="ast-flow-line" v-if="verification.evidence"><strong>证据：</strong>{{ verification.evidence }}</div>
                          </div>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">涉及页面</div>
                        <div class="modal-value mono">
                          <template v-if="selectedFinding.urls && selectedFinding.urls.length">
                            {{ selectedFinding.urls.join(' | ') }}
                          </template>
                          <template v-else>
                            {{ selectedFinding.url }}
                          </template>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">漏洞类型</div>
                        <div class="modal-value">{{ selectedFinding.kind_display || selectedFinding.kind }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">最终判断</div>
                        <div class="modal-value">
                          <span class="pill" :class="'assessment_' + selectedFinding.final_assessment">
                            {{ selectedFinding.final_assessment_label || selectedFinding.final_assessment }}
                          </span>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">人工状态</div>
                        <div class="status-row">
                          <select class="input status-select" :value="selectedFinding.review_status || 'open'" @change="updateFindingStatus($event.target.value)">
                            <option value="open">待处理</option>
                            <option value="confirmed">人工确认</option>
                            <option value="false_positive">误报</option>
                            <option value="fixed">已修复</option>
                            <option value="ignored">已忽略</option>
                          </select>
                          <span class="muted-inline">{{ selectedFinding.review_status_label || '待处理' }}</span>
                        </div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.summary">
                        <div class="modal-label">聚合总结</div>
                        <div class="modal-value">{{ selectedFinding.summary }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.instance_count">
                        <div class="modal-label">命中数量</div>
                        <div class="modal-value">{{ selectedFinding.instance_count }} 处</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">漏洞证据 / 源码片段</div>
                        <div class="code-block">{{ selectedFinding.evidence }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.instances && selectedFinding.instances.length">
                        <div class="modal-label">命中位置</div>
                        <div class="instance-list">
                          <div class="instance-item" v-for="(item, idx) in selectedFinding.instances" :key="'finding-instance-' + idx">
                            <div class="instance-meta">
                              <span v-if="item.url">{{ item.url }}</span>
                              <span>第 {{ item.line || '-' }} 行</span>
                              <span v-if="item.label">标记：{{ item.label }}</span>
                            </div>
                            <div class="code-block">{{ item.snippet }}</div>
                            <div v-if="item.flow_display || item.source || item.sink" class="ast-flow-block">
                              <div class="ast-flow-title">AST 命中链路</div>
                              <div class="ast-flow-line" v-if="item.source"><strong>输入源：</strong>{{ item.source }}</div>
                              <div class="ast-flow-line" v-if="item.path && item.path.length"><strong>传播路径：</strong>{{ item.path.join(' -> ') }}</div>
                              <div class="ast-flow-line" v-if="item.sink"><strong>危险汇点：</strong>{{ item.sink }}</div>
                              <div class="ast-flow-line" v-if="item.flow_display"><strong>完整链路：</strong>{{ item.flow_display }}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.confidence">
                        <div class="modal-label">置信度</div>
                        <div class="modal-value">{{ selectedFinding.confidence_label || selectedFinding.confidence }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedFinding.final_assessment_reason">
                        <div class="modal-label">融合判断说明</div>
                        <div class="modal-value">{{ selectedFinding.final_assessment_reason }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">发现时间</div>
                        <div class="modal-value">{{ formatDateTime(selectedFinding.created_at) }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">风险分析</div>
                        <div class="modal-value">
                          <p>涉及页面数量：{{ selectedFinding.page_count || ((selectedFinding.urls && selectedFinding.urls.length) || 1) }}</p>
                          <p>风险类型：{{ selectedFinding.kind_display || selectedFinding.kind }}</p>
                          <p>严重程度：{{ selectedFinding.severity_label || selectedFinding.severity }}</p>
                          <p>{{ selectedFinding.reason || '该页面存在需要进一步复核的潜在风险信号。' }}</p>
                          <p>建议：{{ selectedFinding.recommendation || '请结合输入来源和输出位置继续确认风险。' }}</p>
                        </div>
                      </div>
                    </div>

                    <div v-else-if="selectedAiReport" class="section">
                      <div class="sectionTitle">AI分析详情</div>
                      <div class="modal-section">
                        <div class="modal-label">目标页面</div>
                        <div class="modal-value mono">{{ selectedAiReport.page_url }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">分析时间</div>
                        <div class="modal-value">{{ formatDateTime(selectedAiReport.created_at) }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">分析摘要</div>
                        <div class="modal-value">{{ selectedAiReport.summary }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedAiReport.accuracy">
                        <div class="modal-label">测试准确性</div>
                        <div class="modal-value">{{ selectedAiReport.accuracy }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedAiReport.risk_assessment">
                        <div class="modal-label">风险评估</div>
                        <div class="modal-value">{{ selectedAiReport.risk_assessment }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedAiReport.suggestions && selectedAiReport.suggestions.length">
                        <div class="modal-label">改进建议</div>
                        <ul class="ai-report-list">
                          <li v-for="(s, i) in selectedAiReport.suggestions" :key="'detail-ai-suggestion-' + i">{{ s }}</li>
                        </ul>
                      </div>
                      <div class="modal-section" v-if="selectedAiReport.full_report">
                        <div class="modal-label">详细报告</div>
                        <div class="ai-report-full">{{ selectedAiReport.full_report }}</div>
                      </div>
                    </div>

                    <div v-else-if="selectedVerification" class="section">
                      <div class="sectionTitle">动态验证详情</div>
                      <div class="modal-section">
                        <div class="modal-label">验证结论</div>
                        <div class="modal-value">{{ selectedVerification.summary }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">等级</div>
                        <div class="modal-value">
                          <span class="pill" :class="'sev_' + (selectedVerification.level === 'confirmed' ? 'high' : selectedVerification.level === 'suspected' ? 'medium' : 'low')">
                            {{ selectedVerification.level_label || selectedVerification.level }}
                          </span>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">来源页面</div>
                        <div class="modal-value mono">{{ selectedVerification.page_url }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">验证目标地址</div>
                        <div class="modal-value mono">{{ selectedVerification.target_url }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">向量 / 参数</div>
                        <div class="modal-value">{{ selectedVerification.vector }} / {{ selectedVerification.parameter_name || '-' }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">验证 Payload</div>
                        <div class="modal-value mono">{{ selectedVerification.payload }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">验证时间</div>
                        <div class="modal-value">{{ formatDateTime(selectedVerification.created_at) }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">风险说明</div>
                        <div class="modal-value">{{ selectedVerification.risk }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">修复建议</div>
                        <div class="modal-value">{{ selectedVerification.recommendation }}</div>
                      </div>
                      <div class="modal-section" v-if="selectedVerification.evidence">
                        <div class="modal-label">命中证据</div>
                        <div class="code-block">{{ selectedVerification.evidence }}</div>
                      </div>
                    </div>

                    <!-- 页面详细信息 -->
                    <div v-else-if="selectedPage" class="section">
                      <div class="sectionTitle">页面详情</div>
                      <div class="modal-section">
                        <div class="modal-label">页面 URL</div>
                        <div class="modal-value mono" style="font-weight: 700;">{{ selectedPage.url }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="row">
                          <div class="col">
                            <div class="modal-label">HTTP 状态码</div>
                            <div class="modal-value">{{ selectedPage.status_code }}</div>
                          </div>
                          <div class="col">
                            <div class="modal-label">内容类型</div>
                            <div class="modal-value">{{ selectedPage.content_type }}</div>
                          </div>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">内容 SHA256</div>
                        <div class="modal-value mono">{{ selectedPage.sha256 }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">抓取时间</div>
                        <div class="modal-value">{{ formatDateTime(selectedPage.fetched_at) }}</div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">页面分析</div>
                        <div class="modal-value">
                          <p>页面已成功抓取，状态码：{{ selectedPage.status_code }}</p>
                          <p>内容类型：{{ selectedPage.content_type }}</p>
                          <p>该页面已被扫描，可能存在的XSS漏洞已在发现列表中显示。</p>
                        </div>
                      </div>
                      <div class="modal-section">
                        <div class="modal-label">页面复测</div>
                        <div class="retest-card">
                          <div class="retest-toolbar">
                            <button class="topActionBtn retest-btn" :disabled="retestingFinding" @click="runRetestFromControls()">
                              {{ retestingFinding ? '复测中...' : '单点复测' }}
                            </button>
                            <select class="input retest-select" v-model="selectedRetestPreset" @change="applyRetestPreset()">
                              <option v-for="item in retestPayloadOptions" :key="item.value" :value="item.value">
                                {{ item.label }}
                              </option>
                            </select>
                            <select class="input retest-vector-select" v-model="selectedRetestVector">
                              <option value="">自动判断向量</option>
                              <option value="query">query</option>
                              <option value="form">form</option>
                              <option value="hash">hash</option>
                            </select>
                          </div>
                          <div class="retest-custom-row" v-if="selectedRetestPreset === '__custom__'">
                            <input
                              class="input retest-custom-input"
                              v-model="customRetestPayload"
                              type="text"
                              placeholder="输入自定义 payload，留空则使用系统默认值"
                            />
                          </div>
                          <div class="retest-feedback-row">
                            <span class="muted-inline" v-if="findingPayloadSuggestionsLoading">正在预取推荐 payload...</span>
                            <span class="muted-inline" v-else>{{ findingRetestFeedback || '对当前页面做一次轻量复测，结果会显示在这里。' }}</span>
                          </div>
                          <div class="retest-summary-list" v-if="findingRetestResults && findingRetestResults.length">
                            <div class="retest-summary-item" v-for="(item, idx) in findingRetestResults.slice(0, 3)" :key="'retest-result-' + idx">
                              <div class="retest-summary-meta">
                                <span class="pill" :class="'sev_' + (item.level === 'confirmed' ? 'high' : item.level === 'suspected' ? 'medium' : 'low')">
                                  {{ item.level_label || item.level }}
                                </span>
                                <span>{{ item.vector }}</span>
                                <span v-if="item.parameter_name">{{ item.parameter_name }}</span>
                              </div>
                              <div class="retest-summary-text">{{ item.summary }}</div>
                              <div class="retest-summary-text" v-if="item.target_url">目标：{{ item.target_url }}</div>
                            </div>
                            <div class="muted-inline" v-if="findingRetestResults.length > 3">
                              仅展示前 3 条结果。
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="modal-section" v-if="selectedPageFindings && selectedPageFindings.length">
                        <div class="modal-label">页面命中风险</div>
                        <div class="instance-list">
                          <div class="instance-item" v-for="(finding, idx) in selectedPageFindings" :key="'page-finding-' + idx">
                            <div class="instance-meta">
                              <span>{{ finding.title }}</span>
                              <span>{{ finding.severity_label || finding.severity }}</span>
                              <span>{{ finding.instance_count }} 处</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="modal-section" v-if="selectedPage.content">
                        <div class="modal-label">HTML 源码</div>
                        <div v-if="selectedPageHighlightedHtml" class="source-view" v-html="selectedPageHighlightedHtml"></div>
                        <div v-else class="code-block">{{ selectedPage.content }}</div>
                      </div>
                    </div>

                    <!-- 默认提示 -->
                    <div v-else class="muted" style="padding: 20px; text-align: center;">
                      请从左侧列表中选择一个风险点或页面查看详细信息
                    </div>
                  </div>
                </section>
              </div>
            </main>

            <!-- 模态框 -->
            <div v-if="activeModal" class="modal-overlay" @click.self="closeModal">
              <div class="modal">
                <div class="modal-header">
                  <div class="modal-title">
                    {{
                      activeModal.type === 'finding'
                        ? '发现详情'
                        : activeModal.type === 'page'
                          ? '页面详情'
                          : activeModal.type === 'ai'
                            ? 'AI分析详情'
                            : '动态验证详情'
                    }}
                  </div>
                  <button class="modal-close" @click="closeModal">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5">
                      <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                  </button>
                </div>
                <div class="modal-body">
                  <template v-if="activeModal.type === 'finding'">
                    <div class="modal-section">
                      <div class="modal-label">漏洞标题</div>
                      <div class="modal-value" style="font-weight: 700; font-size: 16px;">{{ activeModal.data.title }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">危险等级</div>
                      <div class="modal-value">
                        <span class="pill" :class="'sev_' + activeModal.data.severity">{{ activeModal.data.severity_label || activeModal.data.severity }}</span>
                      </div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">涉及页面</div>
                      <div class="modal-value mono">
                        <template v-if="activeModal.data.urls && activeModal.data.urls.length">
                          {{ activeModal.data.urls.join(' | ') }}
                        </template>
                        <template v-else>
                          {{ activeModal.data.url }}
                        </template>
                      </div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">漏洞证据 / 源码片段</div>
                      <div class="code-block">{{ activeModal.data.evidence }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.confidence">
                      <div class="modal-label">置信度</div>
                      <div class="modal-value">{{ activeModal.data.confidence_label || activeModal.data.confidence }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.instances && activeModal.data.instances.length">
                      <div class="modal-label">命中位置</div>
                      <div class="instance-list">
                        <div class="instance-item" v-for="(item, idx) in activeModal.data.instances" :key="'modal-instance-' + idx">
                          <div class="instance-meta">
                            <span v-if="item.url">{{ item.url }}</span>
                            <span>第 {{ item.line || '-' }} 行</span>
                            <span v-if="item.label">标记：{{ item.label }}</span>
                          </div>
                          <div class="code-block">{{ item.snippet }}</div>
                        </div>
                      </div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">发现时间</div>
                      <div class="modal-value">{{ formatDateTime(activeModal.data.created_at) }}</div>
                    </div>
                  </template>
                  
                  <template v-else-if="activeModal.type === 'ai'">
                    <div class="modal-section">
                      <div class="modal-label">目标页面</div>
                      <div class="modal-value mono">{{ activeModal.data.page_url }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">分析时间</div>
                      <div class="modal-value">{{ formatDateTime(activeModal.data.created_at) }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">分析摘要</div>
                      <div class="modal-value">{{ activeModal.data.summary }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.accuracy">
                      <div class="modal-label">测试准确性</div>
                      <div class="modal-value">{{ activeModal.data.accuracy }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.risk_assessment">
                      <div class="modal-label">风险评估</div>
                      <div class="modal-value">{{ activeModal.data.risk_assessment }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.suggestions && activeModal.data.suggestions.length">
                      <div class="modal-label">改进建议</div>
                      <ul class="ai-report-list">
                        <li v-for="(s, i) in activeModal.data.suggestions" :key="'modal-ai-suggestion-' + i">{{ s }}</li>
                      </ul>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.full_report">
                      <div class="modal-label">详细报告</div>
                      <div class="ai-report-full">{{ activeModal.data.full_report }}</div>
                    </div>
                  </template>

                  <template v-else-if="activeModal.type === 'verification'">
                    <div class="modal-section">
                      <div class="modal-label">验证结论</div>
                      <div class="modal-value">{{ activeModal.data.summary }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">等级</div>
                      <div class="modal-value">
                        <span class="pill" :class="'sev_' + (activeModal.data.level === 'confirmed' ? 'high' : activeModal.data.level === 'suspected' ? 'medium' : 'low')">
                          {{ activeModal.data.level_label || activeModal.data.level }}
                        </span>
                      </div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">来源页面</div>
                      <div class="modal-value mono">{{ activeModal.data.page_url }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">验证目标地址</div>
                      <div class="modal-value mono">{{ activeModal.data.target_url }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">向量 / 参数</div>
                      <div class="modal-value">{{ activeModal.data.vector }} / {{ activeModal.data.parameter_name || '-' }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">验证 Payload</div>
                      <div class="modal-value mono">{{ activeModal.data.payload }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">风险说明</div>
                      <div class="modal-value">{{ activeModal.data.risk }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">修复建议</div>
                      <div class="modal-value">{{ activeModal.data.recommendation }}</div>
                    </div>
                    <div class="modal-section" v-if="activeModal.data.evidence">
                      <div class="modal-label">命中证据</div>
                      <div class="code-block">{{ activeModal.data.evidence }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">验证时间</div>
                      <div class="modal-value">{{ formatDateTime(activeModal.data.created_at) }}</div>
                    </div>
                  </template>

                  <template v-else-if="activeModal.type === 'page'">
                    <div class="modal-section">
                      <div class="modal-label">页面 URL</div>
                      <div class="modal-value mono" style="font-weight: 700;">{{ activeModal.data.url }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="row">
                        <div class="col">
                          <div class="modal-label">HTTP 状态码</div>
                          <div class="modal-value">{{ activeModal.data.status_code }}</div>
                        </div>
                        <div class="col">
                          <div class="modal-label">内容类型</div>
                          <div class="modal-value">{{ activeModal.data.content_type }}</div>
                        </div>
                      </div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">内容 SHA256</div>
                      <div class="modal-value mono">{{ activeModal.data.sha256 }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">抓取时间</div>
                      <div class="modal-value">{{ formatDateTime(activeModal.data.fetched_at) }}</div>
                    </div>
                    <div class="modal-section">
                      <div class="modal-label">查看提示</div>
                      <div class="modal-value">普通视图下仅展示页面概要，切换到详细视图后可查看完整源码和更多信息。</div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        `
