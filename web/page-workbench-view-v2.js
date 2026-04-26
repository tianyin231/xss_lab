export const PAGE_WORKBENCH_TEMPLATE = `
  <div class="workbenchPage" v-if="workbenchData">
    <section class="workbenchHero">
      <div class="workbenchHeroMain">
        <div class="workbenchEyebrow">Page Verification Workbench</div>
        <h2 class="workbenchTitle">页面验证工作台</h2>
        <p class="workbenchText">
          这里把页面输入面画像、关联风险、手工复测、AI 辅助多轮验证、动态验证结果和修复建议放在同一个视角里，
          方便你围绕单个页面做验证、比较和解释。
        </p>
      </div>
      <div class="workbenchHeroMeta">
        <div class="workbenchMetaCard">
          <span class="workbenchMetaLabel">目标页面</span>
          <span class="workbenchMetaValue mono">{{ workbenchData.page.url }}</span>
        </div>
        <div class="workbenchMetaCard">
          <span class="workbenchMetaLabel">关联风险数</span>
          <span class="workbenchMetaValue">{{ workbenchData.risk_summary.total_findings }}</span>
        </div>
        <div class="workbenchMetaCard">
          <span class="workbenchMetaLabel">最高等级</span>
          <span class="workbenchMetaValue">{{ workbenchData.risk_summary.highest_severity_label }}</span>
        </div>
      </div>
    </section>

    <div class="workbenchGrid">
      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">页面基础信息</div>
        <div class="workbenchInfoGrid">
          <div class="workbenchInfoItem">
            <span class="workbenchInfoLabel">HTTP 状态码</span>
            <span class="workbenchInfoValue">{{ workbenchData.page.status_code || '-' }}</span>
          </div>
          <div class="workbenchInfoItem">
            <span class="workbenchInfoLabel">内容类型</span>
            <span class="workbenchInfoValue mono">{{ workbenchData.page.content_type || '-' }}</span>
          </div>
          <div class="workbenchInfoItem">
            <span class="workbenchInfoLabel">抓取时间</span>
            <span class="workbenchInfoValue">{{ formatDateTime(workbenchData.page.fetched_at) }}</span>
          </div>
          <div class="workbenchInfoItem">
            <span class="workbenchInfoLabel">内容摘要</span>
            <span class="workbenchInfoValue mono">{{ workbenchData.page.sha256 || '-' }}</span>
          </div>
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">输入面画像</div>
        <div class="workbenchCluster">
          <div class="workbenchCard">
            <div class="workbenchCardTitle">Query 参数</div>
            <div class="workbenchTagList" v-if="workbenchData.input_profile.query_params.length">
              <span class="workbenchTag" v-for="param in workbenchData.input_profile.query_params" :key="'query-' + param">{{ param }}</span>
            </div>
            <div class="muted-inline" v-else>当前页面 URL 没有显式 query 参数。</div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">表单字段</div>
            <div class="workbenchFormList" v-if="workbenchData.input_profile.forms.length">
              <div class="workbenchFormItem" v-for="(form, idx) in workbenchData.input_profile.forms" :key="'form-' + idx">
                <div class="workbenchFormMeta">
                  <span>{{ form.method.toUpperCase() }}</span>
                  <span class="mono">{{ form.action }}</span>
                </div>
                <div class="workbenchTagList" v-if="form.fields && form.fields.length">
                  <span class="workbenchTag" v-for="field in form.fields" :key="'field-' + idx + '-' + field">{{ field }}</span>
                </div>
              </div>
            </div>
            <div class="muted-inline" v-else>未识别到明显表单字段。</div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">Source 线索</div>
            <div class="workbenchTagList" v-if="workbenchData.input_profile.source_hints.length">
              <span class="workbenchTag" v-for="hint in workbenchData.input_profile.source_hints" :key="'source-' + hint">{{ hint }}</span>
            </div>
            <div class="muted-inline" v-else>当前页面没有识别到明显 source 痕迹。</div>
            <div class="workbenchInlineMeta">
              <span>Hash 使用：{{ workbenchData.input_profile.uses_hash ? '是' : '否' }}</span>
              <span>内联事件：{{ workbenchData.input_profile.inline_event_count }}</span>
              <span>脚本块：{{ workbenchData.input_profile.script_blocks }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">页面风险摘要</div>
        <div class="workbenchStats">
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">关联发现</span>
            <span class="workbenchStatValue">{{ workbenchData.risk_summary.total_findings }}</span>
          </div>
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">动态结果</span>
            <span class="workbenchStatValue">{{ workbenchData.risk_summary.dynamic_result_count }}</span>
          </div>
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">已确认信号</span>
            <span class="workbenchStatValue">{{ workbenchData.risk_summary.verified_result_count }}</span>
          </div>
        </div>
        <div class="workbenchSplit">
          <div class="workbenchCard">
            <div class="workbenchCardTitle">类型分布</div>
            <div class="workbenchList">
              <div class="workbenchListItem" v-for="item in workbenchData.risk_summary.kind_breakdown" :key="'kind-' + item.key">
                <span>{{ item.label }}</span>
                <span>{{ item.count }}</span>
              </div>
            </div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">风险线索</div>
            <div class="workbenchTagList" v-if="workbenchData.risk_summary.risky_api_hints.length">
              <span class="workbenchTag workbenchTagStrong" v-for="hint in workbenchData.risk_summary.risky_api_hints" :key="'hint-' + hint">{{ hint }}</span>
            </div>
            <div class="muted-inline" v-else>当前页面没有特别集中的危险模式。</div>
            <div class="workbenchInlineMeta">
              <span>DOM 汇点：{{ workbenchData.risk_summary.dom_sink_hits }}</span>
              <span>内联事件：{{ workbenchData.risk_summary.inline_event_hits }}</span>
              <span>动态验证：{{ workbenchData.risk_summary.has_dynamic_verification ? '有' : '无' }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">单点复测</div>
        <div class="workbenchCallout" v-if="workbenchData.retest_strategy">
          <div><strong>自动选择说明：</strong>{{ workbenchData.retest_strategy.reason }}</div>
          <div v-if="workbenchData.retest_strategy.preferred_vector"><strong>推荐向量：</strong>{{ workbenchData.retest_strategy.preferred_vector }}</div>
          <div v-if="workbenchData.retest_strategy.preferred_payload" class="mono"><strong>默认探针：</strong>{{ workbenchData.retest_strategy.preferred_payload.payload }}</div>
        </div>
        <div class="workbenchCluster" v-if="workbenchData.successful_payloads && workbenchData.successful_payloads.length">
          <div class="workbenchCard" v-for="(item, idx) in workbenchData.successful_payloads" :key="'successful-payload-' + idx">
            <div class="workbenchCardTitle">成功 Payload {{ idx + 1 }}</div>
            <div class="muted-inline">{{ item.level_label || item.level }} / {{ item.vector || '-' }} / {{ item.parameter_name || '-' }}</div>
            <div class="workbenchResultTitle mono">{{ item.payload }}</div>
            <div class="muted-inline" v-if="item.why_it_worked">{{ item.why_it_worked }}</div>
            <div class="muted-inline" v-if="item.construction && item.construction.request_construction">{{ item.construction.request_construction }}</div>
            <div class="muted-inline mono" v-if="item.construction && item.construction.after_target">{{ item.construction.after_target }}</div>
            <div class="muted-inline mono" v-if="item.construction && item.construction.mutated_part">{{ item.construction.mutated_part }}</div>
            <div class="muted-inline" v-if="item.reflection_snippet">命中片段：{{ item.reflection_snippet }}</div>
            <div class="muted-inline" v-if="item.target_url">目标：{{ item.target_url }}</div>
            <div class="code-block" v-if="item.construction && item.construction.markup_construction">{{ item.construction.markup_construction }}</div>
            <div class="code-block" v-if="item.construction && item.construction.snippet_before">{{ item.construction.snippet_before }}</div>
            <div class="code-block" v-if="item.construction && item.construction.snippet_after">{{ item.construction.snippet_after }}</div>
            <div class="actions" style="margin-top: 12px;">
              <button class="topActionBtn" @click="applySuccessfulPayload(item)">带入复测</button>
              <button class="topActionBtn topActionBtnSecondary" @click="copyToClipboard(item.payload, 'Payload 已复制')">复制 Payload</button>
              <button class="topActionBtn topActionBtnSecondary" v-if="item.target_url" @click="copyToClipboard(item.target_url, '目标地址已复制')">复制目标 URL</button>
            </div>
          </div>
        </div>
        <div class="retest-card workbenchRetestCard">
          <div class="retest-toolbar">
            <button class="topActionBtn retest-btn" :disabled="workbenchRetesting" @click="runWorkbenchRetest()">
              {{ workbenchRetesting ? '复测中...' : '开始复测' }}
            </button>
            <select class="input retest-select" v-model="workbenchSelectedPreset" @change="applyWorkbenchRetestPreset()">
              <option v-for="item in workbenchRetestPayloadOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <select class="input retest-vector-select" v-model="workbenchSelectedVector">
              <option value="">自动判断向量</option>
              <option value="query">query</option>
              <option value="form">form</option>
              <option value="hash">hash</option>
            </select>
          </div>
          <div class="retest-custom-row" v-if="workbenchSelectedPreset === '__custom__'">
            <input
              class="input retest-custom-input"
              v-model="workbenchCustomPayload"
              type="text"
              placeholder="输入自定义 payload，留空则使用系统默认值"
            />
          </div>
          <div class="retest-feedback-row">
            <span class="muted-inline">{{ workbenchRetestFeedback || '会基于当前页面的输入面做一次轻量复测。' }}</span>
          </div>
          <div class="workbenchReportHeader" v-if="currentRetestReport">
            <div class="muted-inline">
              当前报告：{{ formatDateTime(currentRetestReport.created_at) }} / {{ currentRetestReport.result_count }} 条结果
            </div>
          </div>
          <div class="retest-summary-list" v-if="currentRetestReport && currentRetestReport.results.length">
            <div class="retest-summary-item" v-for="(item, idx) in currentRetestReport.results" :key="'workbench-retest-' + currentRetestReport.batch_id + '-' + idx">
              <div class="retest-summary-meta">
                <span class="pill" :class="'sev_' + (item.level === 'confirmed' ? 'high' : item.level === 'suspected' ? 'medium' : 'low')">
                  {{ item.level_label || item.level }}
                </span>
                <span>{{ item.vector }}</span>
                <span v-if="item.parameter_name">{{ item.parameter_name }}</span>
                <span class="workbenchMetaBadge" :class="{ strong: item.reflection_found }">
                  {{ item.reflection_found ? '已发现回显' : '未发现回显' }}
                </span>
                <span class="workbenchMetaBadge" v-if="item.reflection_context_label">{{ item.reflection_context_label }}</span>
                <button
                  v-if="item.id"
                  type="button"
                  class="workbenchInlineDangerBtn"
                  :disabled="deletingRetestResultId === String(item.id)"
                  @click="deleteRetestResult(item.id)"
                >
                  {{ deletingRetestResultId === String(item.id) ? '删除中...' : '删除' }}
                </button>
              </div>
              <div class="retest-summary-text">{{ item.summary }}</div>
              <div class="retest-summary-text" v-if="item.context_hint">说明：{{ item.context_hint }}</div>
              <div class="retest-summary-text" v-if="item.evidence">证据：{{ item.evidence }}</div>
              <div class="retest-summary-text" v-if="item.reflection_snippet">命中片段：{{ item.reflection_snippet }}</div>
              <div class="retest-summary-text" v-if="item.target_url">目标：{{ item.target_url }}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">关联发现</div>
        <div class="workbenchFindingList" v-if="workbenchData.related_findings.length">
          <article class="workbenchFindingCard" v-for="item in workbenchData.related_findings" :key="'related-' + item.id">
            <div class="workbenchFindingHeader">
              <span class="pill" :class="'sev_' + item.severity">{{ item.severity_label }}</span>
              <span class="mono">{{ item.kind_display }}</span>
            </div>
            <div class="workbenchFindingTitle">{{ item.title }}</div>
            <div class="workbenchFindingEvidence">{{ item.evidence }}</div>
          </article>
        </div>
        <div class="muted-inline" v-else>当前页面没有关联发现。</div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">复测记录</div>
        <div class="workbenchList" v-if="workbenchData.manual_retest_reports && workbenchData.manual_retest_reports.length">
          <article
            class="workbenchListItem workbenchResultItem workbenchReportItem"
            :class="{ active: selectedRetestReportId === item.batch_id }"
            v-for="item in workbenchData.manual_retest_reports"
            :key="'manual-report-' + item.batch_id"
            @click="selectRetestReport(item.batch_id)"
          >
            <div>
              <div class="workbenchResultTitle">{{ formatDateTime(item.created_at) }}</div>
              <div class="muted-inline">{{ item.result_count }} 条结果 / 向量：{{ item.vectors.join(', ') || '-' }}</div>
              <div class="muted-inline" v-if="item.reason">{{ item.reason }}</div>
            </div>
            <div class="workbenchReportActions">
              <span class="workbenchMetaBadge strong">{{ item.status_summary.confirmed }} 已确认</span>
              <span class="workbenchMetaBadge">{{ item.status_summary.not_triggered }} 未触发</span>
            </div>
          </article>
        </div>
        <div class="muted-inline" v-else>当前页面还没有复测记录。</div>
      </section>

      <section class="workbenchPanel" v-if="currentRetestReport && compareRetestReport && retestComparison">
        <div class="workbenchSectionTitle">结果对比</div>
        <div class="workbenchCompareToolbar">
          <div class="workbenchCompareMeta">
            <div class="muted-inline">当前报告：{{ formatDateTime(currentRetestReport.created_at) }}</div>
            <div class="muted-inline">对比报告：</div>
          </div>
          <select class="input workbenchCompareSelect" :value="selectedCompareReportId" @change="selectCompareReport($event.target.value)">
            <option v-for="item in compareCandidateReports" :key="'compare-' + item.batch_id" :value="item.batch_id">
              {{ formatDateTime(item.created_at) }} / {{ item.result_count }} 条结果
            </option>
          </select>
        </div>
        <div class="workbenchStats workbenchCompareStats">
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">状态变化</span>
            <span class="workbenchStatValue">{{ retestComparison.summary.changed }}</span>
          </div>
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">仅当前存在</span>
            <span class="workbenchStatValue">{{ retestComparison.summary.onlyCurrent }}</span>
          </div>
          <div class="workbenchStatCard">
            <span class="workbenchStatLabel">仅历史存在</span>
            <span class="workbenchStatValue">{{ retestComparison.summary.onlyCompare }}</span>
          </div>
        </div>
        <div class="workbenchCompareGrid">
          <div class="workbenchCard">
            <div class="workbenchCardTitle">状态或回显发生变化</div>
            <div class="workbenchCompareList" v-if="retestComparison.changed.length">
              <article class="workbenchCompareItem" v-for="item in retestComparison.changed" :key="'changed-' + item.key">
                <div class="workbenchCompareTitle">{{ item.label }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag current">当前</span>
                  <span>{{ item.current.level_label }}</span>
                  <span>{{ item.current.reflection_found ? '有回显' : '无回显' }}</span>
                  <span v-if="item.current.reflection_context_label">{{ item.current.reflection_context_label }}</span>
                </div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag compare">历史</span>
                  <span>{{ item.compare.level_label }}</span>
                  <span>{{ item.compare.reflection_found ? '有回显' : '无回显' }}</span>
                  <span v-if="item.compare.reflection_context_label">{{ item.compare.reflection_context_label }}</span>
                </div>
              </article>
            </div>
            <div class="muted-inline" v-else>这两份报告在共同向量上的状态与回显没有明显变化。</div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">结果集合差异</div>
            <div class="workbenchCompareList" v-if="retestComparison.onlyCurrent.length || retestComparison.onlyCompare.length">
              <article class="workbenchCompareItem" v-for="item in retestComparison.onlyCurrent" :key="'only-current-' + item.key">
                <div class="workbenchCompareTitle">{{ item.label }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag current">仅当前</span>
                  <span>{{ item.item.level_label }}</span>
                  <span>{{ item.item.reflection_found ? '有回显' : '无回显' }}</span>
                </div>
              </article>
              <article class="workbenchCompareItem" v-for="item in retestComparison.onlyCompare" :key="'only-compare-' + item.key">
                <div class="workbenchCompareTitle">{{ item.label }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag compare">仅历史</span>
                  <span>{{ item.item.level_label }}</span>
                  <span>{{ item.item.reflection_found ? '有回显' : '无回显' }}</span>
                </div>
              </article>
            </div>
            <div class="muted-inline" v-else>这两份报告的结果集合一致，没有新增或缺失的向量/参数组合。</div>
          </div>
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">AI解释</div>
        <div class="workbenchCallout">
          <div>这里的 AI 解释不会替换原有 AI 分析，而是专门围绕当前页面、当前复测报告和可选对比报告做讲解。</div>
        </div>
        <div class="workbenchAiToolbar">
          <select class="input workbenchAiSelect" v-model="aiExplainAudience">
            <option value="beginner">面向初学者</option>
            <option value="developer">面向开发者</option>
            <option value="thesis">面向论文描述</option>
          </select>
          <button class="topActionBtn" :disabled="aiExplainLoading" @click="runAIExplain()">
            {{ aiExplainLoading ? '解释生成中...' : '生成 AI 解释' }}
          </button>
        </div>
        <div class="muted-inline" v-if="aiExplainError">AI解释失败：{{ aiExplainError }}</div>
        <div class="workbenchAiResult" v-if="aiExplainResult">{{ aiExplainResult }}</div>
        <div class="muted-inline" v-else-if="!aiExplainLoading">
          这里会把当前页面的风险、复测结果和对比差异翻译成更容易理解的解释。
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">AI辅助多轮验证</div>
        <div class="workbenchCallout">
          <div>这里使用的是安全探针而不是可执行 payload，会按多轮顺序验证 query / form / hash 等输入面，目标是提高判断准确率。</div>
        </div>
        <div class="workbenchAiToolbar">
          <select class="input workbenchAiSelect" v-model="aiValidateMode">
            <option value="quick">快速模式</option>
            <option value="standard">标准模式</option>
            <option value="deep">深度模式</option>
          </select>
          <button class="topActionBtn" :disabled="aiValidateLoading" @click="runAIMultiRoundValidation()">
            {{ aiValidateLoading ? '验证执行中...' : '启动 AI 多轮验证' }}
          </button>
        </div>
        <div class="muted-inline" v-if="aiValidateError">AI多轮验证失败：{{ aiValidateError }}</div>
        <div class="workbenchAiResult" v-if="aiValidateResult">
          <div><strong>本次模式：</strong>{{ aiValidateResult.mode }}</div>
          <div><strong>计划来源：</strong>{{ aiValidateResult.plan_provider === 'ai' ? 'AI推荐' : '系统回退策略' }}</div>
          <div><strong>计划理由：</strong>{{ aiValidateResult.plan_reason }}</div>
        </div>
        <div class="workbenchList" v-if="workbenchData.ai_multi_round_reports && workbenchData.ai_multi_round_reports.length">
          <article
            class="workbenchListItem workbenchResultItem workbenchReportItem"
            :class="{ active: selectedAIMultiRoundReportId === item.batch_id }"
            v-for="item in workbenchData.ai_multi_round_reports"
            :key="'ai-report-' + item.batch_id"
            @click="selectAIMultiRoundReport(item.batch_id)"
          >
            <div>
              <div class="workbenchResultTitle">{{ formatDateTime(item.created_at) }}</div>
              <div class="muted-inline">{{ item.mode || '-' }} / {{ item.plan_provider === 'ai' ? 'AI推荐' : '系统回退' }} / {{ item.result_count }} 条结果</div>
              <div class="muted-inline" v-if="item.reason">{{ item.reason }}</div>
            </div>
            <div class="workbenchReportActions">
              <span class="workbenchMetaBadge strong">{{ item.verified_count }} 已确认</span>
              <span class="workbenchMetaBadge">{{ item.final_assessment_label }}</span>
              <button
                type="button"
                class="workbenchInlineDangerBtn"
                :disabled="deletingAIMultiRoundReportId === item.batch_id"
                @click.stop="deleteAIMultiRoundReport(item.batch_id)"
              >
                {{ deletingAIMultiRoundReportId === item.batch_id ? '删除中...' : '删除' }}
              </button>
            </div>
          </article>
        </div>
        <div class="workbenchCompareGrid workbenchCompareGridWide" v-if="currentAIMultiRoundReport">
          <div class="workbenchCard">
            <div class="workbenchCardTitle">当前多轮验证报告</div>
            <div class="muted-inline">时间：{{ formatDateTime(currentAIMultiRoundReport.created_at) }}</div>
            <div class="muted-inline">模式：{{ currentAIMultiRoundReport.mode || '-' }} / 来源：{{ currentAIMultiRoundReport.plan_provider || '-' }}</div>
            <div class="muted-inline">结果数：{{ currentAIMultiRoundReport.result_count }} / 已确认：{{ currentAIMultiRoundReport.verified_count }}</div>
            <div class="muted-inline" v-if="currentAIMultiRoundReport.reason">理由：{{ currentAIMultiRoundReport.reason }}</div>
            <div class="muted-inline"><strong>最终结论：</strong>{{ currentAIMultiRoundReport.final_assessment_label }}</div>
            <div class="muted-inline" v-if="currentAIMultiRoundReport.final_assessment_reason">{{ currentAIMultiRoundReport.final_assessment_reason }}</div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">验证计划</div>
            <div class="workbenchCompareList" v-if="currentAIMultiRoundReport.rounds && currentAIMultiRoundReport.rounds.length">
              <article class="workbenchCompareItem" v-for="item in currentAIMultiRoundReport.rounds" :key="'ai-plan-' + item.round_index">
                <div class="workbenchCompareTitle">{{ item.round_label || ('第 ' + item.round_index + ' 轮') }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag current">{{ item.vector || '-' }}</span>
                  <span>{{ item.payload || '-' }}</span>
                </div>
                <div class="muted-inline" v-if="item.round_reason">{{ item.round_reason }}</div>
                <div class="muted-inline">结果数：{{ item.result_count }} / 已确认：{{ item.confirmed_count }}</div>
              </article>
            </div>
            <div class="muted-inline" v-else>当前没有可展示的轮次计划。</div>
          </div>
          <div class="workbenchCard" v-if="currentAIMultiRoundReport.plan_analysis">
            <div class="workbenchCardTitle">计划与实际</div>
            <div class="muted-inline"><strong>贡献最大的一轮：</strong>{{ currentAIMultiRoundReport.plan_analysis.best_round_label || '-' }}</div>
            <div class="muted-inline"><strong>最有效向量：</strong>{{ currentAIMultiRoundReport.plan_analysis.best_vector || '-' }}</div>
            <div class="muted-inline" v-if="currentAIMultiRoundReport.plan_analysis.key_parameter"><strong>关键参数：</strong>{{ currentAIMultiRoundReport.plan_analysis.key_parameter }}</div>
            <div class="muted-inline"><strong>最强信号：</strong>{{ currentAIMultiRoundReport.plan_analysis.strongest_signal_label || '-' }}</div>
            <div class="muted-inline" v-if="currentAIMultiRoundReport.plan_analysis.strongest_signal_reason">
              {{ currentAIMultiRoundReport.plan_analysis.strongest_signal_reason }}
            </div>
            <div class="workbenchCompareList" v-if="currentAIMultiRoundReport.plan_analysis.expectations && currentAIMultiRoundReport.plan_analysis.expectations.length">
              <article class="workbenchCompareItem" v-for="item in currentAIMultiRoundReport.plan_analysis.expectations" :key="'ai-expect-' + item.round_index">
                <div class="workbenchCompareTitle">{{ item.round_label }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag current">{{ item.status_label }}</span>
                  <span>{{ item.vector || '-' }}</span>
                  <span>{{ item.confirmed_count }} 已确认 / {{ item.suspected_count }} 可疑</span>
                </div>
                <div class="muted-inline">{{ item.reason }}</div>
              </article>
            </div>
          </div>
          <div class="workbenchCard">
            <div class="workbenchCardTitle">轮次结果</div>
            <div class="workbenchCompareList" v-if="currentAIMultiRoundReport.results && currentAIMultiRoundReport.results.length">
              <article class="workbenchCompareItem" v-for="item in currentAIMultiRoundReport.results" :key="'ai-round-' + item.id">
                <div class="workbenchCompareTitle">{{ item.round_label || '多轮验证' }} / {{ item.vector || '-' }} / {{ item.parameter_name || '-' }}</div>
                <div class="workbenchCompareRow">
                  <span class="workbenchCompareTag current">{{ item.level_label }}</span>
                  <span>{{ item.reflection_found ? '有回显' : '无回显' }}</span>
                  <span v-if="item.reflection_context_label">{{ item.reflection_context_label }}</span>
                </div>
                <div class="muted-inline" v-if="item.round_reason">{{ item.round_reason }}</div>
              </article>
            </div>
            <div class="muted-inline" v-else>当前还没有 AI 多轮验证结果。</div>
          </div>
        </div>
        <div class="muted-inline" v-else-if="!aiValidateLoading">
          启动后会自动执行多轮安全探针验证，并把最新结果保存在工作台中。
        </div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">动态验证结果</div>
        <div class="workbenchList" v-if="workbenchData.dynamic_results.length">
          <div class="workbenchListItem workbenchResultItem" v-for="item in workbenchData.dynamic_results" :key="'dynamic-' + item.id">
            <div>
              <div class="workbenchResultTitle">{{ item.summary }}</div>
              <div class="muted-inline">{{ item.vector }} / {{ item.parameter_name || '-' }}</div>
              <div class="muted-inline" v-if="item.reflection_context_label">{{ item.reflection_found ? '回显上下文：' : '上下文提示：' }}{{ item.reflection_context_label }}</div>
              <div class="muted-inline" v-if="item.context_hint">{{ item.context_hint }}</div>
            </div>
            <span class="pill" :class="'sev_' + (item.level === 'confirmed' ? 'high' : item.level === 'suspected' ? 'medium' : 'low')">
              {{ item.level_label }}
            </span>
          </div>
        </div>
        <div class="muted-inline" v-else>当前页面还没有动态验证历史结果。</div>
      </section>

      <section class="workbenchPanel">
        <div class="workbenchSectionTitle">修复建议</div>
        <ul class="workbenchSuggestionList">
          <li v-for="(item, idx) in workbenchData.repair_suggestions" :key="'repair-' + idx">{{ item }}</li>
        </ul>
      </section>

      <section class="workbenchPanel" v-if="workbenchData.page.content">
        <div class="workbenchSectionTitle">HTML 源码</div>
        <div class="code-block workbenchSourceBlock">{{ workbenchData.page.content }}</div>
      </section>
    </div>
  </div>
`
