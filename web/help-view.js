export const HELP_VIEW_TEMPLATE = `
  <div class="helpPage">
    <section class="helpHero">
      <div class="helpHeroBadge">Knowledge Base</div>
      <div class="helpHeroTitle">帮助与知识库</div>
      <div class="helpHeroText">
        这里集中解释系统里的关键名词、探测方式、结果含义、攻击原理和常见疑问。
        它不是百科全书，而是一个面向当前工具的阅读入口，帮助你更快看懂结果和判断依据。
      </div>
      <div class="helpStats">
        <div class="helpStat">
          <span class="helpStatLabel">分类</span>
          <span class="helpStatValue">{{ helpSections.length }}</span>
        </div>
        <div class="helpStat">
          <span class="helpStatLabel">条目</span>
          <span class="helpStatValue">{{ helpEntryCount }}</span>
        </div>
        <div class="helpStat">
          <span class="helpStatLabel">当前筛选</span>
          <span class="helpStatValue">{{ helpCategoryLabel }}</span>
        </div>
      </div>
      <div class="helpFilters">
        <select class="input helpCategorySelect" v-model="helpCategory">
          <option v-for="item in helpCategories" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <input class="input helpSearch" v-model="helpQuery" placeholder="搜索名词、原理、字段、FAQ..." />
      </div>
      <div class="helpHighlights">
        <article class="helpHighlightCard">
          <div class="helpHighlightLabel">快速理解</div>
          <div class="helpHighlightTitle">先看系统怎么工作</div>
          <div class="helpHighlightText">第一次使用时，建议先看“系统怎么工作”和“结果怎么理解”。</div>
        </article>
        <article class="helpHighlightCard">
          <div class="helpHighlightLabel">重点关注</div>
          <div class="helpHighlightTitle">页面复测是页面级工具</div>
          <div class="helpHighlightText">它验证的是页面输入面，不是单个 finding 标题本身，所以多个发现可能共享同一组复测结果。</div>
        </article>
        <article class="helpHighlightCard">
          <div class="helpHighlightLabel">阅读方式</div>
          <div class="helpHighlightTitle">优先围绕当前系统阅读</div>
          <div class="helpHighlightText">这里优先解释系统中真实出现的字段、术语和判断逻辑，而不是泛化地讲所有安全知识。</div>
        </article>
      </div>
    </section>

    <div class="helpLayout">
      <aside class="helpSidebar">
        <div class="helpSidebarTitle">知识分类</div>
        <button
          v-for="item in helpCategories"
          :key="'help-nav-' + item.value"
          class="helpNavBtn"
          :class="{ active: helpCategory === item.value }"
          @click="helpCategory = item.value"
        >
          <span>{{ item.label }}</span>
          <span class="helpNavCount" v-if="item.value !== 'all'">
            {{ (helpSections.find(section => section.key === item.value)?.items || []).length }}
          </span>
        </button>
      </aside>

      <section class="helpContent">
        <div v-if="!filteredHelpSections.length" class="helpEmpty">
          没有找到匹配内容，请换个关键词试试。
        </div>
        <div v-for="section in filteredHelpSections" :key="section.key" class="helpSection">
          <div class="helpSectionHeader">
            <div class="helpSectionTitle">{{ section.label }}</div>
            <div class="helpSectionMeta">{{ section.items.length }} 条内容</div>
          </div>
          <div class="helpFaqList">
            <article
              v-for="item in section.items"
              :key="item.id"
              class="helpFaqCard clickable"
              :class="{ expanded: isHelpItemExpanded(item.id) }"
              @click="toggleHelpItem(item.id)"
            >
              <div class="helpFaqQuestion">
                <span>{{ item.q }}</span>
                <span class="helpFaqToggle">{{ isHelpItemExpanded(item.id) ? '收起' : '展开' }}</span>
              </div>
              <div class="helpTagRow">
                <span v-for="tag in item.tags" :key="item.id + '-' + tag" class="helpTag">{{ tag }}</span>
              </div>
              <div v-if="isHelpItemExpanded(item.id)" class="helpFaqAnswer">
                <p v-for="(paragraph, pidx) in (item.details && item.details.length ? item.details : [item.a])" :key="item.id + '-p-' + pidx">
                  {{ paragraph }}
                </p>
                <ul v-if="item.bullets && item.bullets.length" class="helpBulletList">
                  <li v-for="(point, bidx) in item.bullets" :key="item.id + '-b-' + bidx">{{ point }}</li>
                </ul>
              </div>
              <div v-if="item.resources && item.resources.length" class="helpResourceBlock">
                <div class="helpResourceTitle">延伸阅读</div>
                <div class="helpResourceList">
                  <a
                    v-for="resource in item.resources"
                    :key="item.id + '-' + resource.href"
                    class="helpResourceLink"
                    :href="resource.href"
                    target="_blank"
                    rel="noreferrer noopener"
                    @click.stop
                  >
                    {{ resource.label }}
                  </a>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  </div>
`
