export const HELP_SECTIONS = [
  {
    key: 'terms',
    label: '基础名词',
    items: [
      {
        id: 'term_xss',
        q: '什么是 XSS？',
        a: 'XSS 是把不可信输入带入页面并被浏览器当成可执行内容处理的一类问题。',
        details: [
          '最核心的本质是“输入被当成代码或可解释内容执行”，而不是“页面里出现了特殊字符”这么简单。',
          '如果外部输入最终进入 HTML、事件属性、脚本字符串、URL 协议等可执行上下文，就可能形成 XSS。',
          '这个系统的很多发现项，本质上都是在寻找“输入有没有机会进入危险上下文”。'
        ],
        bullets: [
          'XSS 不一定已经成功利用，但一定意味着页面存在值得继续验证的风险路径。',
          '扫描结果里的 payload、source、sink、上下文，都是围绕这条风险路径展开的。'
        ],
        tags: ['XSS', '基础概念', '漏洞原理'],
        resources: [
          { label: 'OWASP 中文：跨站脚本预防速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' },
          { label: 'OWASP: Cross Site Scripting (XSS)', href: 'https://owasp.org/www-community/attacks/xss/' },
          { label: 'PortSwigger: What is XSS?', href: 'https://portswigger.net/web-security/cross-site-scripting' }
        ]
      },
      {
        id: 'term_dom_xss',
        q: '什么是 DOM XSS？',
        a: 'DOM XSS 指风险完全发生在浏览器端，JavaScript 在运行时把不可信输入送进危险汇点。',
        details: [
          '这类问题通常不依赖服务端把 payload 原样回显，而是前端脚本自己从 URL、hash、storage、postMessage 等地方取值再写入页面。',
          '常见危险汇点包括 innerHTML、outerHTML、insertAdjacentHTML、document.write、eval 一类 API。',
          'DOM XSS 的难点在于它往往隐藏在 JavaScript 代码流里，所以静态分析时通常会结合 AST、数据传播线索和危险 API 规则。'
        ],
        bullets: [
          '常见 source：location.search、location.hash、document.URL、postMessage、localStorage',
          '常见 sink：innerHTML、outerHTML、insertAdjacentHTML、document.write、eval'
        ],
        tags: ['DOM XSS', 'Source', 'Sink'],
        resources: [
          { label: 'OWASP 中文：基于 DOM 的 XSS 预防', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html' },
          { label: 'OWASP: DOM Based XSS', href: 'https://owasp.org/www-community/attacks/DOM_Based_XSS' },
          { label: 'OWASP: DOM based XSS Prevention Cheat Sheet', href: 'https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html' }
        ]
      },
      {
        id: 'term_types',
        q: '反射型、存储型、DOM 型 XSS 有什么区别？',
        a: '三者的区别主要在输入存放的位置、触发时机，以及浏览器最终是怎么拿到这段恶意内容的。',
        details: [
          '反射型 XSS 一般是请求进来后服务端立刻拼回响应里，用户访问特制链接就会触发。',
          '存储型 XSS 一般是恶意内容先被保存到数据库、评论、资料页等位置，后续其他用户访问页面时再被执行。',
          'DOM 型 XSS 不一定经过服务端回显，而是前端脚本自己把输入带入危险汇点。'
        ],
        bullets: [
          '反射型更像“请求即触发”。',
          '存储型更像“先写入，再被其他页面读取并执行”。',
          'DOM 型更像“前端脚本在浏览器里把数据变成了可执行内容”。'
        ],
        tags: ['反射型 XSS', '存储型 XSS', 'DOM XSS'],
        resources: [
          { label: 'PortSwigger: Reflected XSS', href: 'https://portswigger.net/web-security/cross-site-scripting/reflected' },
          { label: 'PortSwigger: Stored XSS', href: 'https://portswigger.net/web-security/cross-site-scripting/stored' },
          { label: 'PortSwigger: DOM-based XSS', href: 'https://portswigger.net/web-security/cross-site-scripting/dom-based' }
        ]
      },
      {
        id: 'term_source_sink',
        q: 'Source 和 Sink 分别是什么意思？',
        a: 'Source 是不可信输入的来源，Sink 是把这些输入变成可执行或可解释内容的位置。',
        details: [
          'Source 可以理解成“数据从哪里进来”，例如 location.search、location.hash、Cookie、表单、接口返回等。',
          'Sink 可以理解成“数据最后被放到哪里”，例如 innerHTML 会把字符串当成 HTML 解释，eval 会把字符串当成代码执行。',
          '很多扫描规则都不是单看 source 或单看 sink，而是关注“source 是否可能流向 sink”。'
        ],
        bullets: [
          '只有 source 不一定危险，因为输入可能被安全处理了。',
          '只有 sink 也不一定危险，因为送进去的内容可能是常量或可信数据。',
          '真正需要重点关注的是可控输入到危险汇点之间的传播链。'
        ],
        tags: ['Source', 'Sink', '数据流'],
        resources: [
          { label: 'PortSwigger: DOM XSS sources and sinks', href: 'https://portswigger.net/web-security/cross-site-scripting/dom-based' }
        ]
      },
      {
        id: 'term_context',
        q: '什么是输出上下文？为什么它很重要？',
        a: '同一段输入放到不同位置，浏览器的解释方式完全不同，所以验证 payload 也必须跟着上下文变化。',
        details: [
          '输入出现在 HTML 文本区、属性值、script 字符串、URL 协议位置时，浏览器的解析规则都不同。',
          '很多看起来一样的 payload，只在特定上下文里才会触发，换个位置就可能完全无效。',
          '因此系统在解释结果或推荐 payload 时，会强调“这是哪种上下文”，而不是只给一个统一的攻击字符串。'
        ],
        bullets: [
          'HTML 文本上下文常见关注标签注入。',
          '属性上下文常见关注引号逃逸和事件属性。',
          'JavaScript 上下文常见关注字符串闭合、模板字符串和执行函数。'
        ],
        tags: ['上下文', '输出位置', '解释方式'],
        resources: [
          { label: 'MDN 中文：element.innerHTML', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Element/innerHTML' },
          { label: 'OWASP XSS Prevention Cheat Sheet', href: 'https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' }
        ]
      },
      {
        id: 'term_payload',
        q: 'Payload 是什么？',
        a: 'Payload 是用来验证某个输入点是否能进入危险上下文的一段测试内容。',
        details: [
          '在轻量验证工具里，payload 更像“探针”，目的是观察页面如何处理输入，而不是为了真的执行破坏性行为。',
          '不同上下文需要不同 payload，例如 HTML 标签注入、属性闭合、JavaScript 字符串闭合、javascript: 协议等都属于不同验证方向。',
          '系统里的推荐 payload 只是候选项，不代表它一定命中，也不代表没命中就绝对安全。'
        ],
        bullets: [
          'payload 的意义是帮助你判断“输入有没有被带到危险位置”。',
          'payload 需要和上下文、向量、页面行为一起看，不能孤立理解。'
        ],
        tags: ['Payload', '验证探针'],
        resources: [
          { label: 'PortSwigger: XSS cheat sheet', href: 'https://portswigger.net/web-security/cross-site-scripting/cheat-sheet' }
        ]
      },
      {
        id: 'term_inline_handler',
        q: '什么是内联事件？为什么系统会重点提示？',
        a: '内联事件指把 JavaScript 直接写在 HTML 属性里，例如 onclick、onload、onerror。',
        details: [
          '这类写法会让“HTML 属性”和“可执行脚本”之间的边界变得很弱，一旦输入能进入属性值，就可能进一步影响执行逻辑。',
          '很多历史问题都和内联事件、字符串拼接模板、动态构造标签一起出现。',
          '所以系统把内联事件相关模式当成高价值线索，它不一定直接等于漏洞，但通常值得优先复核。'
        ],
        bullets: [
          '常见示例：onclick、onload、onerror、onmouseover',
          '如果输入能进入这些属性，风险通常高于普通纯文本回显'
        ],
        tags: ['内联事件', '事件属性'],
        resources: [
          { label: 'MDN: Global event handlers', href: 'https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes#list_of_global_event_handler_attributes' }
        ]
      }
    ]
  },
  {
    key: 'workflow',
    label: '系统怎么工作',
    items: [
      {
        id: 'workflow_scan',
        q: '这个系统的整体工作流程是什么？',
        a: '主流程可以概括为：创建任务 -> 爬取页面 -> 提取特征 -> 生成发现 -> 动态验证 -> 汇总展示。',
        details: [
          '用户先输入目标网址和扫描参数，系统创建一个任务并开始爬取页面。',
          '页面被抓取后，系统会记录 URL、状态码、内容类型、源码内容等基础信息，并针对 HTML 与 JavaScript 做轻量分析。',
          '分析阶段会根据危险 API、内联事件、DOM 数据流、可疑拼接模式等规则生成发现项。',
          '之后系统可以对部分结果做动态验证或页面复测，把“静态怀疑”进一步转成更直观的验证信息。',
          '最后所有信息会汇总到报告、页面详情、发现详情和帮助页面里。'
        ],
        bullets: [
          '它更像“轻量验证工具”，不是工业级持续扫描平台。',
          '重点是帮助你更快定位、解释和复核风险，而不是覆盖一切场景。'
        ],
        tags: ['系统流程', '工作原理', '扫描'],
        resources: []
      },
      {
        id: 'workflow_crawl',
        q: '系统是如何爬取页面的？',
        a: '系统会从目标入口开始，按设定深度和页面数限制逐步发现并抓取同域页面。',
        details: [
          '它会优先保留和任务相关的页面信息，包括 URL、状态码、内容类型、抓取时间和页面源码。',
          '对于 HTML 页面，后续步骤会进一步提取脚本、表单、内联事件、链接等特征；对于脚本资源，则更关注 JavaScript 代码里的危险模式。',
          '系统并不是为了做超大型资产测绘，而是为了给当前验证任务提供足够的页面样本。'
        ],
        bullets: [
          '深度决定链接继续向下跟进的层级。',
          '页数决定这次任务最多抓取多少页面。',
          'Selenium 是可选项，用于更贴近真实浏览器行为的场景。'
        ],
        tags: ['爬取', '页面采集', '任务参数'],
        resources: [
          { label: 'MDN: Document Object Model', href: 'https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model' }
        ]
      },
      {
        id: 'workflow_findings',
        q: '系统是怎么生成发现项的？',
        a: '发现项来自规则命中和轻量数据流分析，本质上是在记录“哪里值得怀疑”。',
        details: [
          '它会关注危险汇点、DOM 赋值链、字符串拼接、内联事件、可疑模板片段等模式。',
          '如果某条规则命中，会生成一个发现项，里面通常包含标题、类型、级别、证据、页面 URL 和命中位置。',
          '为了让报告更易读，系统还会把多个相近命中做聚合，所以你在报告里看到的是“聚合后的发现”，不一定等于数据库里最原始的一条记录。'
        ],
        bullets: [
          '发现项是“值得复核的线索”，不是百分之百已经成立的漏洞。',
          '聚合后的展示更适合阅读，但复核时要记得它背后可能对应多条原始命中。'
        ],
        tags: ['发现项', '规则', '聚合'],
        resources: []
      },
      {
        id: 'workflow_verify',
        q: '动态验证和页面复测分别是什么？',
        a: '动态验证更像系统自动做的一轮验证，页面复测则是你基于某个已爬取页面做一次手工辅助验证。',
        details: [
          '动态验证通常跟随扫描结果一起出现，用于把部分静态命中再做一轮自动确认。',
          '页面复测是当前工具箱功能，目标是对某个已爬取页面的输入面再做一次轻量尝试，看看 query、form、hash 等向量是否有明显响应。',
          '因为页面复测本质是页面级动作，所以多个发现项落在同一页面时，复测结果可能相同或高度相似。'
        ],
        bullets: [
          '动态验证更偏系统自动流程。',
          '页面复测更偏人工辅助验证。'
        ],
        tags: ['动态验证', '页面复测'],
        resources: []
      },
      {
        id: 'workflow_retest_tool',
        q: '“单点复测”这个工具具体是做什么的？',
        a: '它是一个页面级的轻量验证工具，用来快速判断某个已爬取页面的输入面是否会对测试 payload 产生可疑响应。',
        details: [
          '它不会重新做整站扫描，也不是完整浏览器渗透流程，而是围绕当前页面做一次很小范围的验证尝试。',
          '系统会把 payload 带入 query、form 或 hash 这样的输入向量，再观察目标地址、响应摘要、证据和结果等级。',
          '它的价值主要在于帮助你把“静态发现”快速转成“页面级验证线索”，让你知道下一步该优先看哪里。'
        ],
        bullets: [
          '它回答的是“这个页面值不值得继续深挖”。',
          '它不是漏洞利用器，而是一个辅助验证器。'
        ],
        tags: ['单点复测', '页面级工具', '验证作用'],
        resources: []
      },
      {
        id: 'workflow_report',
        q: '报告、页面列表和发现列表分别在看什么？',
        a: '三者是同一批扫描数据的不同视角：报告看整体，页面列表看页面，发现列表看风险线索。',
        details: [
          '报告视角更适合总览任务结果，例如总页面数、总发现数、动态验证结果、AI 分析结果等。',
          '页面列表适合按具体页面查看源码、命中风险和页面级复测结果。',
          '发现列表适合从漏洞线索角度看标题、级别、最终判断、人工状态和证据。'
        ],
        bullets: [
          '如果你关心“这个页面到底发生了什么”，优先看页面详情。',
          '如果你关心“这类问题有哪些、严重性如何”，优先看发现列表。'
        ],
        tags: ['报告', '页面列表', '发现列表'],
        resources: []
      }
    ]
  },
  {
    key: 'system-principles',
    label: '系统运作原理',
    items: [
      {
        id: 'system_architecture',
        q: '从第一性原理看，这个系统到底在做什么？',
        a: '它在回答两个问题：哪里可能有 XSS 风险？这些风险有没有足够证据值得进一步相信？',
        details: [
          '第一步是发现线索，找出输入、危险汇点、上下文和页面行为之间可能存在的风险关系。',
          '第二步是增强证据，通过动态验证、页面复测、人工状态和最终判断，把“原始命中”整理成更可解释的结果。',
          '所以系统的价值不只是“扫到了什么”，更是“为什么这样判断、你下一步该怎么看”。'
        ],
        bullets: [
          '这是一个面向验证与解释的工具，而不是资产管理平台。',
          '重点是帮助你更快完成定位、理解和复核。'
        ],
        tags: ['系统定位', '原理'],
        resources: []
      },
      {
        id: 'system_runner',
        q: 'Runner 在系统里承担什么角色？',
        a: 'Runner 负责把扫描任务真正跑起来，并把页面、发现、日志等结果持续写回系统。',
        details: [
          '它会消费扫描过程中的事件，例如抓到页面、命中规则、产生动态验证结果、记录运行日志等。',
          '前端看到的实时日志和最终报告，本质上都依赖 Runner 在后台把这些运行信息逐步落库。',
          '因此 Runner 更像任务执行器，而 API 更像数据组织和展示出口。'
        ],
        bullets: [
          'Runner 关心执行过程。',
          'API 关心读取、聚合和对前端提供结果。'
        ],
        tags: ['Runner', '任务执行', '后台流程'],
        resources: []
      },
      {
        id: 'system_grouping',
        q: '为什么系统要做发现聚合？',
        a: '如果完全按原始命中展示，报告会非常碎，很多同类问题会把页面淹没。',
        details: [
          '聚合的目的，是把相近的标题、类型、页面和证据整理成一条更易读的结果。',
          '它降低了阅读成本，也更适合人工复核和导出报告。',
          '但聚合的代价是：一条展示结果背后可能对应多条原始记录，所以在解释某个 finding 时要意识到它不一定只对应一个精确代码点。'
        ],
        bullets: [
          '聚合提升可读性。',
          '原始记录仍然更适合做细粒度排查。'
        ],
        tags: ['聚合', '报告可读性', '原始记录'],
        resources: []
      },
      {
        id: 'system_page_vs_finding',
        q: '为什么现在把复测工具放在页面详情，而不是发现详情？',
        a: '因为复测验证的对象本质上是页面输入面，而不是发现标题本身。',
        details: [
          '多个 finding 往往都落在同一个 HTML 页面上，复测时真正被验证的是 query、form、hash、DOM 行为等页面级输入面。',
          '如果把复测绑定在 finding 上，多个 finding 就很容易重复触发相同的验证，得到几乎一样的结果。',
          '放在页面详情下，语义更准确，也更符合你实际复核页面的方式。'
        ],
        bullets: [
          '页面复测回答的是“这个页面还能不能被轻量触发”。',
          '发现详情回答的是“这条风险线索为什么会被判出来”。'
        ],
        tags: ['页面视角', '发现视角', '复测设计'],
        resources: []
      },
      {
        id: 'system_review',
        q: '人工状态和最终判断为什么同时存在？',
        a: '因为系统判断和人工判断承担的是不同角色：前者给出自动化结论，后者记录你的复核意见。',
        details: [
          '最终判断通常来自规则、动态验证和聚合逻辑，是系统基于证据做出的自动化归纳。',
          '人工状态则代表你的复核结果，例如待处理、人工确认、误报、已修复、已忽略。',
          '两者并存能帮助你区分“系统怎么看”和“你最终怎么定”。'
        ],
        bullets: [
          '系统判断用于快速筛选。',
          '人工状态用于最终管理和解释结果。'
        ],
        tags: ['人工复核', '最终判断', '状态流转'],
        resources: []
      }
    ]
  },
  {
    key: 'results',
    label: '结果怎么理解',
    items: [
      {
        id: 'result_severity',
        q: '严重程度代表什么？',
        a: '严重程度是系统对风险影响面的粗粒度排序，不是法律意义上的最终定级。',
        details: [
          '它通常综合考虑危险汇点、上下文、可利用性线索和历史经验来给出一个更直观的优先级。',
          '高危通常意味着更接近可利用执行，或影响面更直接；中低危则可能只是线索较强但证据还不充分。',
          '在这个工具里，严重程度主要用于帮助你安排复核顺序。'
        ],
        bullets: [
          '先看高危，但不要忽略中危里那些命中证据很实的结果。',
          '严重程度不是绝对真理，仍要结合证据和页面行为理解。'
        ],
        tags: ['严重程度', '优先级'],
        resources: []
      },
      {
        id: 'result_confidence',
        q: '置信度是什么意思？',
        a: '置信度代表系统对“这条发现值得相信到什么程度”的内部信心。',
        details: [
          '它不是漏洞利用成功率，也不是 CVSS 一类外部评分。',
          '如果命中证据更具体、source 与 sink 关系更明确、动态验证也提供了支持，置信度通常会更高。',
          '如果只命中了较宽泛的模式，没有更多上下文补强，置信度通常会偏低。'
        ],
        bullets: [
          '高置信度适合优先复核。',
          '低置信度不等于误报，只是代表证据还比较弱。'
        ],
        tags: ['置信度', '证据强弱'],
        resources: []
      },
      {
        id: 'result_assessment',
        q: '最终判断、人工状态、动态验证结论应该怎么看？',
        a: '它们分别回答三件事：系统初步判断是什么、你人工复核后怎么定、动态验证有没有补充证据。',
        details: [
          '最终判断更像系统的自动结论，例如风险较强、需复核、动态仅观察到弱信号等。',
          '人工状态是你最终如何处理这条结果，例如待处理、人工确认、误报、已修复、已忽略。',
          '动态验证结论则是系统尝试触发后得到的附加证据，它能增强判断，但不应该机械替代人工分析。'
        ],
        bullets: [
          '先看证据，再看系统判断。',
          '人工状态是最终管理视角下最关键的一层。'
        ],
        tags: ['最终判断', '人工状态', '动态验证'],
        resources: []
      },
      {
        id: 'result_page_hits',
        q: '页面命中风险是什么意思？',
        a: '它表示当前页面关联到了哪些发现项，帮助你从页面视角理解风险分布。',
        details: [
          '一个页面可能同时命中多个不同类型的线索，例如内联事件、DOM sink、可疑拼接模板等。',
          '页面命中风险并不是说页面上存在多个独立漏洞，而是表示该页面上存在多条值得关注的风险信号。',
          '结合页面源码和页面复测结果一起看，通常会比只盯着 finding 标题更清晰。'
        ],
        bullets: [
          '页面命中风险更适合排查页面整体情况。',
          '发现列表更适合按漏洞类型做归类和筛选。'
        ],
        tags: ['页面命中风险', '页面详情'],
        resources: []
      },
      {
        id: 'result_dynamic_levels',
        q: '为什么动态验证会出现 confirmed / suspected / not_triggered？',
        a: '这是系统对验证结果强弱的分层表达，而不是简单的“成功 / 失败”。',
        details: [
          'confirmed 通常表示动态验证已经观察到较强的触发证据或结果反馈。',
          'suspected 通常表示看到了一些可疑迹象，但还不足以完全确认。',
          'not_triggered 通常表示这轮尝试没有看到明显触发信号，但这不等于页面绝对安全。'
        ],
        bullets: [
          '动态验证是补充证据，不是绝对裁判。',
          '验证没触发，可能是 payload、上下文、页面状态或时机不匹配。'
        ],
        tags: ['动态验证', '结果等级'],
        resources: []
      }
    ]
  },
  {
    key: 'principles',
    label: '攻击与探测原理',
    items: [
      {
        id: 'principle_innerhtml',
        q: '为什么 innerHTML、document.write 这类 API 危险？',
        a: '因为它们会把字符串直接当成 HTML 解释，等于把“普通文本”升级成了“浏览器可解析内容”。',
        details: [
          '只要外部输入有机会进入这类 API，浏览器就可能创建新的标签、属性和事件处理逻辑。',
          '如果再叠加上下文逃逸、属性注入、事件属性等条件，就更容易形成可执行风险。',
          '所以很多 DOM XSS 规则都会把这类 API 作为重点 sink。'
        ],
        bullets: [
          'innerHTML 更偏 DOM 写入。',
          'document.write 更偏文档流拼接。',
          '两者都属于高价值危险汇点。'
        ],
        tags: ['innerHTML', 'document.write', '危险 API'],
        resources: [
          { label: 'MDN: Element.innerHTML', href: 'https://developer.mozilla.org/en-US/docs/Web/API/Element/innerHTML' },
          { label: 'MDN: Document.write', href: 'https://developer.mozilla.org/en-US/docs/Web/API/Document/write' }
        ]
      },
      {
        id: 'principle_protocol',
        q: '为什么 javascript:、data:、srcdoc 这类位置也危险？',
        a: '因为这些位置天然带有“内容解释”能力，一旦把不可信输入放进去，浏览器可能会按脚本或文档来处理。',
        details: [
          '例如 javascript: 协议会把后续内容当成脚本执行，srcdoc 会把内容当成 iframe 内联文档解析。',
          '即便不一定立即触发，只要输入进入了这些位置，就说明页面对危险上下文的控制比较弱。',
          '系统把它们当成重要线索，是因为它们通常具有较高的利用潜力。'
        ],
        bullets: [
          '危险不只在 script 标签里。',
          'URL 协议位和文档位同样可能成为执行入口。'
        ],
        tags: ['javascript:', 'data:', 'srcdoc'],
        resources: [
          { label: 'MDN: iframe srcdoc', href: 'https://developer.mozilla.org/en-US/docs/Web/API/HTMLIFrameElement/srcdoc' }
        ]
      },
      {
        id: 'principle_vectors',
        q: 'query、form、hash 三种向量有什么区别？',
        a: '它们都是输入进入页面的路径，但进入页面的方式和典型使用场景不同。',
        details: [
          'query（查询参数验证）：逐个替换URL查询参数进行测试，最常见，也最容易与反射型或 DOM 型处理逻辑结合。',
          'form（表单验证）：统一填充表单所有字段进行测试，适合测试页面提交、回显、客户端拼接逻辑。',
          'hash（片段标识符验证）：基于URL片段（#号后内容）的注入测试，来自 location.hash，常用于前端路由、片段定位和纯浏览器端 DOM 处理。'
        ],
        bullets: [
          ' query 方法:',
          '原始URL: http://example.com/page?name=John&age=25&city=Beijing',
          '1. http://example.com/page?name=<script>alert(1)</script>&age=25&city=Beijing',
          '2. http://example.com/page?name=John&age=<script>alert(1)</script>&city=Beijing  ',
          '3. http://example.com/page?name=John&age=25&city=<script>alert(1)</script>',
          ' form 方法:',
          '<form method="POST" action="/submit">',
          '< input name = "username" value = "" >',
          '<input name="email" value="">',
          '<textarea name="comment"></textarea>',
          '</form>',
          'POST /submit',
          'username=<script>alert(1)</script>',
          'email=<script>alert(1)</script>',
          'comment=<script>alert(1)</script>',
          'hash 方法:',
          '原始URL: http://example.com/page',
          '生成测试URL: http://example.com/page#<script>alert(1)</script>',

          '如果页面大量依赖前端路由，hash 往往很重要。',
          '如果页面有搜索框、过滤器、表单回显，form 和 query 更值得优先试。'
        ],
        tags: ['query', 'form', 'hash', '输入向量'],
        resources: []
      },
      {
        id: 'principle_payload_context',
        q: '为什么推荐 payload 会随着上下文变化？',
        a: '因为不同上下文有不同的语法边界，只有贴合当前边界的 payload 才有验证价值。',
        details: [
          'HTML 上下文更关注标签和属性构造；JavaScript 上下文更关注字符串闭合、表达式拼接和执行函数；URL 位置则更关注协议与跳转解释。',
          '如果把 JavaScript 字符串 payload 直接拿去测 HTML 文本区，结果通常没有意义。',
          '所以推荐 payload 的目的不是“更炫”，而是让验证更贴近当前页面的真实解析方式。'
        ],
        bullets: [
          'payload 不是越复杂越好。',
          '最重要的是贴合上下文和页面行为。'
        ],
        tags: ['上下文', 'Payload', '验证策略'],
        resources: [
          { label: 'PortSwigger: XSS contexts', href: 'https://portswigger.net/web-security/cross-site-scripting/contexts' }
        ]
      },
      {
        id: 'principle_retest_payloads',
        q: '单点复测里的内置 payload 实际在测什么？',
        a: '内置 payload 本质上是一组轻量探针，分别去试探不同上下文是否会把输入当成 HTML、属性、脚本或协议来解释。',
        details: [
          '例如 HTML 标签注入类 payload 会测试页面是否把输入直接拼进可解析的标签内容中；属性闭合类 payload 会测试输入能否跳出原有属性边界；JavaScript 字符串类 payload 会测试脚本拼接是否存在闭合和执行机会。',
          '还有一些 payload 更偏向 URL / 协议位探测，例如观察 javascript: 一类位置是否被带入危险上下文；也有一些更偏通用探针，用来确认输入是否可达、是否被回显、是否被 DOM 读取。',
          '这些 payload 不追求花哨，而是尽量覆盖当前系统最常见的几类页面风险模式，让结果更容易解释。'
        ],
        bullets: [
          'HTML 探针：更关注标签和节点构造。',
          '属性探针：更关注引号逃逸和事件属性。',
          '脚本探针：更关注字符串闭合、表达式拼接和执行链路。',
          '协议探针：更关注 URL 协议位和跳转解释。'
        ],
        tags: ['单点复测', 'Payload', '探针原理'],
        resources: [
          { label: 'PortSwigger: XSS cheat sheet', href: 'https://portswigger.net/web-security/cross-site-scripting/cheat-sheet' },
          { label: 'PortSwigger: XSS contexts', href: 'https://portswigger.net/web-security/cross-site-scripting/contexts' }
        ]
      },
      {
        id: 'principle_retest_auto_selection',
        q: '系统自动选择 payload 和向量的方式是什么？',
        a: '系统不是随机挑一个 payload，而是根据当前页面线索、页面类型和已有发现特征，选更贴近当前场景的候选项。',
        details: [
          '如果页面更像普通 URL 驱动页面，系统通常会优先考虑 query；如果页面有明显表单或回显交互，会更倾向 form；如果页面更像前端路由或 DOM 驱动页面，则 hash 的优先级会更高。',
          '在 payload 选择上，系统会结合页面已有发现、证据内容、标题关键词和常见危险模式做一个粗粒度上下文判断，例如更像 HTML、属性、脚本字符串还是协议位。',
          '最终给出的推荐项，本质上是“当前页面最值得先试的几种探针”，而不是严格穷举所有可能的攻击方式。'
        ],
        bullets: [
          '先粗分向量，再粗分上下文。',
          '推荐结果追求“更像当前页面”，不是“绝对最强 payload”。',
          '如果自动推荐不合适，仍然可以手动改 payload 做进一步验证。'
        ],
        tags: ['单点复测', '自动选择', '向量判断', '推荐逻辑'],
        resources: []
      },
      {
        id: 'principle_reflection_context',
        q: '什么是回显定位和上下文提示？',
        a: '回显定位是看 payload 有没有出现在响应里；上下文提示则是在说明它大概落在 HTML 文本、属性、脚本还是其他位置。',
        details: [
          '如果 payload 被直接回显，系统会尽量判断它更像出现在 HTML 文本、HTML 属性、script 代码块或注释附近。',
          '这个判断是轻量级的，不等于完整浏览器执行证明，但能帮助你更快知道“输入到底被带到了哪里”。',
          '上下文提示的意义在于帮助你选择下一步更合适的 payload 和人工复核方向，而不是直接替代全部漏洞判断。'
        ],
        bullets: [
          '回显定位回答“payload 有没有被带回来”。',
          '上下文提示回答“payload 大概落在什么位置”。'
        ],
        tags: ['回显定位', '上下文提示', '单点复测'],
        resources: [
          { label: 'PortSwigger: XSS contexts', href: 'https://portswigger.net/web-security/cross-site-scripting/contexts' }
        ]
      }
    ]
  },
  {
    key: 'defense',
    label: '修复与防护',
    items: [
      {
        id: 'defense_encoding',
        q: '面对 XSS，最根本的修复思路是什么？',
        a: '最根本的思路不是“拦截几个 payload”，而是确保不可信输入不会以危险方式进入浏览器解释器。',
        details: [
          '如果页面只是显示文本，就应该把输入当文本输出，而不是拼到 innerHTML 之类的接口里。',
          '如果必须拼接 DOM，优先使用 textContent、createElement、setAttribute 等更可控的方式。',
          '如果必须处理富文本或复杂模板，则要在进入危险上下文之前做严格的上下文敏感防护。'
        ],
        bullets: [
          '不要把黑名单过滤当作最终修复。',
          '优先从输出方式和危险 API 使用方式上修。'
        ],
        tags: ['修复', '输出安全', '防护思路'],
        resources: [
          { label: 'OWASP 中文：跨站脚本预防速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' },
          { label: 'OWASP XSS Prevention Cheat Sheet', href: 'https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' }
        ]
      },
      {
        id: 'defense_frontend',
        q: '前端代码里有哪些更安全的替代方式？',
        a: '核心思路是少用会把字符串当 HTML 或脚本解释的接口，多用结构化、文本化的写法。',
        details: [
          '能用 textContent 就不要用 innerHTML。',
          '能用 createElement + appendChild 就不要直接拼一大段 HTML 字符串。',
          '不要把事件逻辑写在 onclick 一类内联属性里，尽量用 addEventListener。',
          '对 href、src 这类属性要额外检查协议和值来源。'
        ],
        bullets: [
          'innerHTML -> textContent / DOM API',
          '内联事件 -> addEventListener',
          '字符串模板拼接 -> 显式创建节点和属性'
        ],
        tags: ['前端修复', '安全替代'],
        resources: [
          { label: 'MDN 中文：Node.textContent', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Node/textContent' },
          { label: 'MDN 中文：EventTarget.addEventListener', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/EventTarget/addEventListener' },
          { label: 'MDN 中文：element.innerHTML', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Element/innerHTML' }
        ]
      },
      {
        id: 'defense_csp',
        q: 'CSP 对 XSS 有什么帮助？',
        a: 'CSP 可以减少部分脚本执行面，但它更像一层额外防线，不能替代代码层修复。',
        details: [
          '合理的 CSP 可以限制内联脚本、外部脚本来源和某些高风险执行方式。',
          '但如果页面本身仍然把不可信输入送进危险上下文，CSP 也不一定能完全兜住。',
          '因此最稳的顺序永远是：先修代码，再考虑用 CSP 作为补强。'
        ],
        bullets: [
          'CSP 能提升容错，不是根治方案。',
          '如果系统里已经发现明显危险 sink，优先修 sink。'
        ],
        tags: ['CSP', '防护'],
        resources: [
          { label: 'MDN 中文：内容安全策略 CSP', href: 'https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CSP' },
          { label: 'OWASP 中文：内容安全策略速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Content_Security_Policy_Cheat_Sheet.html' }
        ]
      }
    ]
  },
  {
    key: 'external-cn',
    label: '中文外部资料',
    items: [
      {
        id: 'cn_links_xss_prevention',
        q: '想系统学习 XSS 修复，应该按什么顺序学？',
        a: '优先看防护原则和上下文编码资料，再看具体案例，不要一开始就只背 payload 列表。',
        details: [
          'XSS 修复的核心不是记住某几个过滤规则，而是理解输出上下文、危险 DOM API、编码位置和浏览器解释规则。',
          '如果你要把本系统的扫描结果写进论文或答辩材料，建议先阅读 OWASP 的 XSS 预防速查表，再结合 MDN 的 DOM API 文档解释具体代码改法。',
          '这些资料适合作为“为什么这样修”的依据：它们强调上下文敏感输出、避免危险 sink、使用文本化 DOM API、CSP 作为补充防线。',
          '非官方中文教程可以帮助你快速建立直觉，但具体修复结论仍应回到 OWASP、MDN 和项目实际代码。'
        ],
        bullets: [
          '先看 OWASP XSS 预防速查表，建立修复原则。',
          '再看 MDN 的 innerHTML、textContent、addEventListener，落到具体前端代码。',
          '最后看 CSP 资料，把它作为纵深防御补充。'
        ],
        tags: ['中文资料', 'XSS 修复', '学习路线'],
        resources: [
          { label: 'OWASP 中文：跨站脚本预防速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' },
          { label: 'MDN 中文：element.innerHTML', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Element/innerHTML' },
          { label: 'MDN 中文：Node.textContent', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Node/textContent' },
          { label: 'MDN 中文：内容安全策略 CSP', href: 'https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CSP' },
          { label: '非官方中文学习：XSS 从入门到精通（博客园）', href: 'https://www.cnblogs.com/L-xy/p/19085240' },
          { label: '非官方中文学习：XSS 跨站脚本攻击漏洞（博客园）', href: 'https://www.cnblogs.com/wuhongbin/p/15583717.html' }
        ]
      },
      {
        id: 'cn_links_dom_xss',
        q: 'DOM XSS 和 source/sink 分析可以参考哪些中文资料？',
        a: 'DOM XSS 更关注浏览器端 JavaScript 数据流，阅读时要把 source、传播路径和 sink 连起来看。',
        details: [
          'DOM XSS 的重点不只是页面有没有回显，而是前端脚本是否把 location、hash、storage、postMessage 等来源的数据写入 innerHTML、document.write、eval 等危险位置。',
          '本系统里的 source、sink、AST 数据流、页面输入面画像，都可以和 OWASP DOM XSS 预防速查表中的规则对应起来理解。',
          '如果帮助页里的“回显上下文”显示为 HTML 文本、属性或脚本片段，也应该回到 DOM 资料里确认该上下文对应的安全写法。',
          '非官方 DOM XSS 文章往往会列出更多 source 和 sink，适合扩展规则库思路；但实际判断仍要看当前页面是否真的存在可控输入到危险 sink 的链路。'
        ],
        bullets: [
          'source 是数据入口，sink 是危险输出或执行位置。',
          'DOM XSS 常常需要结合源码和运行时行为一起判断。',
          '看到 innerHTML、document.write、eval、事件属性时，优先检查是否有不可信数据流入。'
        ],
        tags: ['中文资料', 'DOM XSS', 'Source', 'Sink'],
        resources: [
          { label: 'OWASP 中文：基于 DOM 的 XSS 预防', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html' },
          { label: 'MDN 中文：Document Object Model', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Document_Object_Model' },
          { label: 'MDN 中文：Document.write', href: 'https://developer.mozilla.org/zh-CN/docs/Web/API/Document/write' },
          { label: '非官方中文学习：HackTricks DOM XSS 中文', href: 'https://book.hacktricks.wiki/zh/pentesting-web/xss-cross-site-scripting/dom-xss.html' },
          { label: '非官方中文学习：DOM XSS 完整指南（博客园译文）', href: 'https://www.cnblogs.com/sec875/p/19324289' }
        ]
      },
      {
        id: 'cn_links_payload_learning',
        q: '学习 payload 时应该避免哪些误区？',
        a: 'payload 是验证工具，不是漏洞本身；只背 payload 很容易误判，也很难解释结果。',
        details: [
          '同一个 payload 在 HTML 文本、属性值、脚本字符串、URL 协议、DOM API 参数里含义完全不同，所以学习 payload 必须和上下文一起学。',
          '本系统把 payload 结果拆成向量、参数、目标 URL、回显状态、上下文提示和证据片段，就是为了避免只看到一串 payload 却不知道它为什么有效。',
          '学习非官方 payload 文章时，建议重点看“它试图闭合什么边界、进入什么上下文、触发什么 sink”，而不是只复制字符串。',
          '如果某个 payload 没命中，也不能直接得出安全结论；可能只是上下文不匹配、输入点不同、页面状态不同或需要浏览器执行。'
        ],
        bullets: [
          '先问：这个 payload 面向哪个上下文？',
          '再问：它验证的是 query、form、hash 还是 DOM source？',
          '最后看：结果里有没有证据支持它真的进入了危险位置？'
        ],
        tags: ['中文资料', 'Payload', '学习误区', '上下文'],
        resources: [
          { label: 'PortSwigger：XSS Cheat Sheet', href: 'https://portswigger.net/web-security/cross-site-scripting/cheat-sheet' },
          { label: '非官方中文学习：常见十大漏洞之 XSS 详解（博客园）', href: 'https://www.cnblogs.com/lukeya/p/14286790.html' },
          { label: '非官方中文学习：Kali Web 渗透测试 SQL 注入与 XSS', href: 'https://kali.wiki/docs/kali/sqli-xss/' }
        ]
      },
      {
        id: 'cn_links_code_audit',
        q: '从代码审计角度看 XSS，应该重点看哪些位置？',
        a: '代码审计时要沿着数据流看：输入从哪里来，经过什么处理，最后写到了哪里。',
        details: [
          '服务端模板重点看变量是否进入 HTML、属性、script、style、URL 等不同输出上下文，以及框架是否默认转义。',
          '前端代码重点看 location、hash、storage、接口返回、postMessage、表单值是否进入 innerHTML、outerHTML、insertAdjacentHTML、document.write、eval、setTimeout 字符串等 sink。',
          '如果项目使用 Vue、React 等框架，也不能只看框架名就认为安全；仍要检查 v-html、dangerouslySetInnerHTML、手写 DOM 操作、第三方富文本渲染等逃逸口。',
          '本系统的静态发现和页面工作台适合辅助定位这些位置，但最终仍要回到源码确认数据流和上下文。'
        ],
        bullets: [
          '审 source：URL、表单、Cookie、Storage、postMessage、接口返回。',
          '审 sink：innerHTML、document.write、eval、事件属性、危险 URL 协议。',
          '审处理过程：有没有正确编码、净化、协议校验和上下文隔离。'
        ],
        tags: ['中文资料', '代码审计', 'Source', 'Sink', '前端安全'],
        resources: [
          { label: '非官方中文学习：DOM XSS 半自动化（博客园）', href: 'https://www.cnblogs.com/piaomiaohongchen/p/16921374.html' },
          { label: '非官方中文学习：XSSStrike 源码分析（CSDN）', href: 'https://blog.csdn.net/2201_75445650/article/details/148352555' },
          { label: 'OWASP 中文：基于 DOM 的 XSS 预防', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html' }
        ]
      },
      {
        id: 'cn_links_csp_and_headers',
        q: 'CSP 和安全响应头应该怎么看？',
        a: 'CSP 是补强措施，适合降低脚本执行面，但不能替代代码层的上下文安全输出。',
        details: [
          'CSP 的价值在于限制脚本来源、内联脚本、eval 等执行面，能够削弱部分 XSS 攻击路径。',
          '但如果页面仍然把不可信输入拼进危险位置，CSP 只能降低风险，不能证明代码本身已经安全。',
          '在论文或报告中描述 CSP 时，建议明确它属于纵深防御：先修 DOM 和输出上下文，再用 CSP、HttpOnly、SameSite 等安全头减少利用面。'
        ],
        bullets: [
          'CSP 优先关注 script-src、default-src、object-src、base-uri 等指令。',
          '开发阶段可以先用 Report-Only 观察违规，再逐步收紧策略。',
          '不要把允许 unsafe-inline 当成长期方案。'
        ],
        tags: ['中文资料', 'CSP', '安全响应头', '纵深防御'],
        resources: [
          { label: 'MDN 中文：内容安全策略 CSP', href: 'https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CSP' },
          { label: 'OWASP 中文：内容安全策略速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Content_Security_Policy_Cheat_Sheet.html' },
          { label: 'OWASP 中国：2024 十大主动安全控制', href: 'https://www.owasp.org.cn/OWASP-CHINA/owasp-project/owasp-proactive-controls4e2d6587987976ee/2024OWASP%E5%8D%81%E5%A4%A7%E4%B8%BB%E5%8A%A8%E5%AE%89%E5%85%A8%E6%8E%A7%E5%88%B6-%E5%8F%91%E5%B8%83%E7%89%88.pdf' }
        ]
      },
      {
        id: 'cn_links_top10_context',
        q: 'OWASP Top 10 和本系统的 XSS 检测有什么关系？',
        a: 'Top 10 是风险分类框架，本系统更聚焦其中与注入、软件和数据完整性、配置缺陷相关的 XSS 检测与验证。',
        details: [
          'XSS 在不同版本和分类里可能被归入注入、客户端脚本风险或更大的应用安全风险类别中；它不是 Top 10 的全部，但一直是 Web 安全中非常典型的问题。',
          '本系统的价值是把 Top 10 这类宏观风险拆到页面、输入向量、payload、证据和修复建议这些可操作对象上。',
          '写论文时可以把 OWASP Top 10 作为研究背景，把本系统的规则扫描、动态验证和报告展示作为具体实现。'
        ],
        bullets: [
          'Top 10 适合写背景和风险分类。',
          '本系统适合展示具体检测、验证和解释流程。',
          '报告里的最终判断仍然要结合具体页面证据。'
        ],
        tags: ['中文资料', 'OWASP Top 10', '论文背景'],
        resources: [
          { label: 'OWASP 中国：Top 10 2021 中文版 PDF', href: 'https://www.owasp.org.cn/OWASP-CHINA/owasp-project/OWASP-TOP10-2021%E4%B8%AD%E6%96%87%E7%89%88V1.0%E5%8F%91%E5%B8%83.pdf' },
          { label: 'OWASP Top 10 2021 繁体中文页面', href: 'https://owasp.org/Top10/2021/zh-Hant/' },
          { label: 'OWASP Cheat Sheet Series', href: 'https://cheatsheetseries.owasp.org/' }
        ]
      },
      {
        id: 'cn_links_thesis_material',
        q: '写论文或答辩时，这些外部资料应该怎么引用和组织？',
        a: '建议把官方资料用于定义和原则，把非官方中文资料用于辅助理解和案例说明。',
        details: [
          '论文背景部分可以引用 OWASP Top 10、OWASP Cheat Sheet、MDN 文档来说明 XSS 的风险、浏览器解释机制和防护原则。',
          '系统设计部分可以结合本项目的爬取、静态分析、动态验证、AI 多轮验证、页面工作台和报告导出，说明你如何把通用安全原则落到工具实现里。',
          '非官方中文文章适合帮助你理解案例和补充表述，但不建议作为唯一权威依据；如果和 OWASP/MDN 的原则不一致，应优先相信官方资料。',
          '答辩展示时可以按“概念 -> 检测流程 -> payload 验证 -> 证据解释 -> 修复建议 -> 外部依据”的顺序组织，这样逻辑更完整。'
        ],
        bullets: [
          '官方资料用于定义、原则和规范依据。',
          '非官方资料用于辅助学习、案例和扩展阅读。',
          '系统截图和报告结果用于证明实现效果。'
        ],
        tags: ['中文资料', '论文', '答辩', '资料组织'],
        resources: [
          { label: 'OWASP 中国：Top 10 2021 中文版 PDF', href: 'https://www.owasp.org.cn/OWASP-CHINA/owasp-project/OWASP-TOP10-2021%E4%B8%AD%E6%96%87%E7%89%88V1.0%E5%8F%91%E5%B8%83.pdf' },
          { label: 'OWASP 中文：跨站脚本预防速查表', href: 'https://cheatsheetseries.owasp.ac.cn/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html' },
          { label: '非官方中文学习：深入解析 XSS 漏洞（博客园）', href: 'https://www.cnblogs.com/yangykaifa/p/19436639' }
        ]
      }
    ]
  },
  {
    key: 'faq',
    label: '常见问题',
    items: [
      {
        id: 'faq_finding_not_equal_vuln',
        q: '每一条发现都等于一个真实漏洞吗？',
        a: '不等于。发现更像是风险线索，代表系统认为这里值得复核。',
        details: [
          '扫描系统为了不漏掉高价值线索，通常会先把可疑模式记录下来，再由动态验证和人工复核继续收敛。',
          '如果一开始就要求每一条发现都百分之百精准，往往会错过很多真实风险路径。',
          '因此更合理的理解方式是：发现项是“候选风险”，最终是否成立要结合证据和上下文确认。'
        ],
        bullets: [
          '发现不是漏洞裁决书。',
          '它是帮助你定位和复核的入口。'
        ],
        tags: ['FAQ', '发现项'],
        resources: []
      },
      {
        id: 'faq_payload_changes',
        q: '为什么同一个页面推荐的 payload 可能变化？',
        a: '因为页面上下文、验证向量和当前线索不同，推荐策略就会跟着变化。',
        details: [
          '如果页面更像 query 驱动的反射或 DOM 读取，推荐会偏向 URL 输入探针；如果页面有明显表单，推荐会更偏 form。',
          '如果页面命中的是属性、内联事件、脚本字符串等不同上下文，payload 形式也会不同。',
          '推荐变化不是系统不稳定，而是系统在尝试贴合当前页面的解析环境。'
        ],
        bullets: [
          '向量不同，payload 会不同。',
          '上下文不同，payload 也会不同。'
        ],
        tags: ['FAQ', 'payload', '推荐策略'],
        resources: []
      },
      {
        id: 'faq_page_retest_same',
        q: '为什么多个发现落在同一页面时，复测结果看起来一样？',
        a: '因为页面复测是页面级动作，验证的是页面输入面，不是某个标题字符串本身。',
        details: [
          '如果多个 finding 指向同一 HTML 页面，它们复测时实际走的常常还是同一组 query、form、hash 或 DOM 行为。',
          '所以得到相同或相似结果是正常现象，不代表系统出错。',
          '也正因为如此，复测工具被放在页面详情下，而不是放在发现详情下。'
        ],
        bullets: [
          '页面复测看页面行为。',
          '发现详情看风险解释。'
        ],
        tags: ['FAQ', '页面复测', '结果重复'],
        resources: []
      },
      {
        id: 'faq_retest_result_meaning',
        q: '单点复测结果里应该重点看什么？',
        a: '优先看目标地址、向量、结果等级、摘要和证据，这几项能最快说明“系统到底观察到了什么”。',
        details: [
          '目标地址可以帮助你确认系统最终把 payload 发到了哪里；向量告诉你是通过 query、form 还是 hash 进入页面；结果等级和摘要则是在概括这次观察的强弱。',
          '如果结果里有证据字段，优先看证据，因为它最接近系统实际观察到的页面反馈或命中现象。',
          '单点复测的结果最好和页面源码、页面命中风险、原始 finding 一起看，这样更容易判断它到底是有效线索、弱信号还是一次未命中的尝试。'
        ],
        bullets: [
          '先看向量和目标地址，确认验证路径。',
          '再看摘要和证据，理解系统为什么给出这个等级。',
          '最后结合源码和发现项做人工判断。'
        ],
        tags: ['FAQ', '单点复测', '结果解释'],
        resources: []
      },
      {
        id: 'faq_dynamic_payload_selection',
        q: '动态验证时，系统是怎么选 payload 的？',
        a: '当前系统选 payload 的过程不是“从列表里随便拿一个”，而是先判断页面有哪些输入向量，再判断哪个向量更值得优先验证，最后才在该向量下挑最贴近当前页面上下文的 payload。',
        details: [
          '第一步，系统先判断页面具备哪些输入面。它会检查 URL 里有没有查询参数、页面源码里有没有表单、脚本里有没有 location.hash 一类痕迹，从而得到当前页面可测的 query、form、hash 向量集合。',
          '第二步，系统再看已有静态线索更偏向哪个向量。比如 finding 证据里出现了 location.search、document.URL、query 等信息时，会更偏向 query；出现 form、input、textarea、select 时，会更偏向 form；出现 location.hash、hashchange 时，会更偏向 hash。',
          '第三步，在已经确定的向量下，系统会从推荐 payload 列表里找最先匹配该向量的 payload。也就是说，query 优先找 query 方向的 payload，form 优先找 form 方向的 payload，hash 优先找 hash 方向的 payload。',
          '第四步，如果当前向量下没有明确匹配的推荐 payload，系统才会退一步，从推荐列表里拿第一个还能用的 payload；如果连推荐列表都给不出有效结果，最后才回退到最基础的默认探针。'
        ],
        bullets: [
          '先判断输入面，再判断优先向量，再选 payload。',
          '推荐 payload 是主入口，默认探针只负责兜底。'
        ],
        tags: ['FAQ', '动态验证', 'payload', '选择机制'],
        resources: []
      },
      {
        id: 'faq_dynamic_injection_method',
        q: '动态验证把 payload 注入到页面里的方式是什么？',
        a: '系统当前采用的是按页面输入面逐步判断的轻量注入方式，不是直接把一个 payload 到处乱打一遍，而是先识别页面有哪些可用输入向量，再按 query、form、hash 的顺序决定怎么注入。',
        details: [
          '第一步是判断当前页面有哪些输入面。系统会先看页面 URL 里有没有查询参数；如果有，就说明 query 向量可以测。然后再看页面 HTML 源码里有没有 <form 标签；如果有，就说明 form 向量可以测。最后再看页面源码和相关线索里有没有 location.hash、hashchange、decodeURIComponent(location.hash) 这类痕迹；如果有，就说明 hash 向量值得测。',
          '第二步是决定优先测哪些向量。系统会先结合已有 finding 的标题、证据、source/sink 线索来猜这个页面更像 query、form 还是 hash 驱动；如果静态线索已经指向某个向量，就先测那个向量。如果静态线索不够明显，再退回到页面本身具备的输入面，也就是“有 query 就测 query，有表单就测 form，有 hash 痕迹就测 hash”。',
          '第三步是按不同向量构造请求。query 模式下，系统会解析 URL 查询参数，逐个参数替换成 payload，其他参数保持不变，因此一次 query 验证通常会生成多次请求，每次只改一个参数。这样做的目的，是尽量知道“到底是哪个参数把 payload 带进了页面”。',
          '第四步是发现和处理表单。系统会直接解析当前页面 HTML，查找所有 <form 元素，然后在每个表单里提取 input、textarea、select 这些可提交字段；像 submit、button、image、reset、file 这类不适合做验证的字段会被跳过。如果一个表单没有可用字段，就不会对它发请求。',
          '第五步是执行 form 注入。对每个表单，系统会读取它的 action 和 method：如果没有 action，就默认提交回当前页面；如果没有 method，就按 GET 处理。然后把当前表单里最多前几个可提交字段统一填成同一个 payload，再按原本的 GET 或 POST 方式请求目标地址。',
          '第六步是处理 hash。hash 模式不会像 query 和 form 那样真正改请求参数，而是把 payload 拼到 URL 的 # 后面，形成新的目标地址。它的核心目的是验证页面前端是否会读取 location.hash 并把它带入 DOM 或脚本逻辑，所以它更偏浏览器侧链路试探。',
          '最后一步才是看页面响应。系统会拿到返回内容后，再判断 payload 有没有回显、回显大概落在什么上下文，并据此给出 confirmed、suspected 或 not_triggered 这类结果。'
        ],
        bullets: [
          '先判断输入面，再决定向量，再构造对应请求。',
          'query 是逐个参数替换，form 是按表单结构填充，hash 是 URL 片段试探。'
        ],
        tags: ['FAQ', '动态验证', '注入方式', 'query', 'form', 'hash'],
        resources: []
      },
      {
        id: 'faq_dynamic_success_judgement',
        q: '系统怎么判断一次动态验证算成功？',
        a: '当前动态验证的成功判定更偏“输入链路和回显证据是否成立”，不是直接以“浏览器里已经弹窗”作为唯一标准。',
        details: [
          '第一步，系统先把请求发出去，拿到返回内容；如果是 GET 并且启用了 Selenium，也可能直接读取浏览器渲染后的页面源码。',
          '第二步，系统会在返回内容里查找 payload 本体、HTML 转义后的 payload、以及常见的引号转义版本。如果能找到这些内容，就说明输入至少被带回到了响应或页面内容里。',
          '第三步，一旦找到命中位置，系统会截取命中前后的一小段片段，作为证据；同时再根据附近结构去粗略猜测上下文更像 HTML 文本、属性、脚本片段还是其他位置。',
          '第四步，系统根据这个结果给状态分级：如果观察到稳定回显，通常会转成 confirmed；如果只是弱信号、hash 线索或不够稳定的场景，通常会转成 suspected；如果没有找到明显命中，就会是 not_triggered；请求过程报错则会记为 error。',
          '所以它真正回答的是“payload 有没有被带回来、带回来后大概落在哪”，而不是自动代替人工宣布漏洞已经完全成立。'
        ],
        bullets: [
          'confirmed 更像“稳定观察到回显并形成较强证据”。',
          'suspected 更像“链路可能存在，但证据还不够硬”。',
          'not_triggered 不等于绝对安全。'
        ],
        tags: ['FAQ', '动态验证', '成功判定', 'confirmed', 'suspected'],
        resources: []
      },
      {
        id: 'faq_retest_payload_mechanism',
        q: '复测功能里的 payload 机制和动态验证有什么关系？',
        a: '两者底层逻辑是同一套页面输入面验证思路，但复测给你的控制权更高：你可以沿用系统推荐、直接复用成功 payload，或者自己指定 payload 和向量。',
        details: [
          '第一种情况是你不手动指定 payload。此时复测会像动态验证一样，先根据当前页面和向量去挑推荐 payload，而不是默认固定只打一条基础探针。',
          '第二种情况是你直接从成功结果继续往下测。现在报告页和工作台都会把成功 payload 单独展示出来，并支持一键带入复测，这样你可以围绕已经命中过的 payload 继续验证同一输入面。',
          '第三种情况是你想手工控制验证。此时你可以自己指定 payload，也可以自己指定 query、form、hash 向量，系统就会跳过自动推荐，按你选的组合直接发起页面级验证。',
          '因此复测更像一个“可操作的验证面板”，而动态验证更像“系统自动先跑一轮”，两者不是互相替代，而是前后衔接。'
        ],
        bullets: [
          '不手改时，复测优先沿用推荐 payload。',
          '已有成功 payload 时，可以直接复用它继续测。',
          '想精细控制时，也可以完全手动指定。'
        ],
        tags: ['FAQ', '复测', 'payload', '成功 payload', '工作台'],
        resources: []
      },
      {
        id: 'faq_ai_multi_round_validation',
        q: 'AI 辅助多轮验证是做什么的？它是怎么运转的？',
        a: 'AI 多轮验证的作用不是直接宣布漏洞成立，而是帮系统在一个页面上更有顺序地尝试多组探针，减少盲试，让“先测什么、后测什么”更像人工分析流程。',
        details: [
          '第一步，系统先收集页面上下文，包括页面 URL、内容类型、输入面画像、风险摘要、关联 finding 和当前候选安全探针。',
          '第二步，系统把这些候选探针交给 AI，请它给出一个多轮计划。这个计划不是让 AI 自己临时编造 payload，而是从系统已经准备好的候选项里挑出更值得优先尝试的几轮，并说明每轮为什么先测它。',
          '第三步，如果 AI 成功给出计划，系统就按 AI 推荐的顺序执行；如果 AI 没有返回可用方案，系统就退回到自己的候选顺序，也就是直接按当前页面最常见、最稳妥的探针顺序去跑。',
          '第四步，系统会把每一轮的向量、payload、原因和结果单独记录下来，所以你最后看到的不只是“有无结果”，而是“第几轮、为什么测它、这一轮出了什么结果”。',
          '第五步，工作台会再把这些轮次结果做汇总，帮你判断哪一轮最匹配当前页面、哪一轮已经出现 confirmed、哪一轮只是部分信号，以及后续最值得继续人工复核的方向。'
        ],
        bullets: [
          'AI 负责推荐轮次顺序，不直接替你裁定漏洞成立。',
          'AI 选的是系统候选探针，不是无限制自由生成。',
          '每一轮都会单独记录，最后再统一汇总。'
        ],
        tags: ['FAQ', 'AI 多轮验证', '验证计划', '工作机制'],
        resources: []
      },
      {
        id: 'faq_payload_fallback',
        q: '什么时候系统会回退到最基础的默认探针？',
        a: '只有当前页面和当前向量下都拿不到更合适的推荐 payload 时，系统才会回退到最基础的默认探针，它的角色更像兜底，而不是主力验证 payload。',
        details: [
          '如果系统已经能判断页面更像 query、form 或 hash 场景，并且推荐列表里有对应向量的 payload，就会优先用这些更贴近场景的候选。',
          '如果推荐列表里没有当前向量的 payload，但还有其他可用推荐项，系统会先尝试这些候选，而不是立刻回到最基础探针。',
          '只有推荐项整体都不够用、或者当前页面的线索太少、实在无法判断该用哪类 payload 时，系统才会启用默认探针，用来先确认输入链路是否存在。'
        ],
        bullets: [
          '默认探针主要负责兜底确认链路。',
          '页面线索越明确，回退到默认探针的概率越低。'
        ],
        tags: ['FAQ', 'payload', 'fallback', '默认探针'],
        resources: []
      },
      {
        id: 'faq_successful_payload_reuse',
        q: '动态验证成功后的 payload，是怎么继续被系统利用的？',
        a: '成功 payload 不会只停留在结果列表里，它会被提炼成更高优先级的复测入口，供你继续围绕同一页面、同一向量、同一参数做验证。',
        details: [
          '系统会先从动态验证结果里筛出 confirmed 或已有明显回显信号的结果，再整理成成功 payload 摘要，单独展示在报告页和页面工作台里。',
          '这些成功 payload 会保留它原来的关键信息，例如向量、参数名、目标地址、上下文提示和命中片段，这样你复测时不会只拿到一个孤立字符串。',
          '当你点击“带入复测”时，系统会把这个 payload 直接填回应的复测输入框，并同步它原本的向量，帮助你继续验证同一条输入路径，而不是重新从零开始试。'
        ],
        bullets: [
          '成功 payload 会被单独提炼出来。',
          '复测时会连同原有向量信息一起带入。'
        ],
        tags: ['FAQ', '成功 payload', '复测', '复用机制'],
        resources: []
      },
      {
        id: 'faq_ai_round_selection',
        q: 'AI 多轮验证里，系统是怎么决定一共跑几轮、每轮测什么的？',
        a: '轮次数量不是固定写死的，而是由当前模式和候选探针数量共同决定；每一轮测什么，则取决于 AI 计划或系统兜底顺序里挑中的候选项。',
        details: [
          '系统先根据 quick、standard、deep 这类模式，决定本次多轮验证最多允许跑多少轮；模式越深，允许的轮数越多。',
          '然后系统会先准备一批候选探针，每个候选项都自带自己的向量、payload、上下文类型和推荐原因。',
          '如果 AI 计划可用，系统就从这些候选项里按 AI 选中的 candidate_id 提取对应轮次；如果 AI 计划不可用，系统就直接按候选列表当前的顺序取前几轮。',
          '所以“每轮测什么”本质上不是随机决定的，而是从系统已经准备好的候选探针中按顺序挑出来执行。'
        ],
        bullets: [
          '模式决定最多跑几轮。',
          '候选探针决定每轮能测什么。',
          'AI 失败时，系统会自动退回兜底轮次顺序。'
        ],
        tags: ['FAQ', 'AI 多轮验证', '轮次', '候选探针'],
        resources: []
      },
      {
        id: 'faq_selenium_dynamic_verify',
        q: 'Selenium 在动态验证里是做什么的？为什么开启和不开启的结果会有出入，哪个更准？',
        a: 'Selenium 的作用，是让动态验证更接近“真实浏览器访问页面”的过程；不开启时更像看原始 HTTP 响应，开启后则会让浏览器真正打开页面、运行脚本、处理 hash 和提交表单，所以两边结果出现差异是正常的。',
        details: [
          '不开启 Selenium 时，系统主要通过普通 HTTP 请求拿响应文本，再检查 payload 有没有出现在返回内容里。这种方式更快、更稳定，但它看到的是“服务器返回了什么”。',
          '开启 Selenium 后，系统会真的驱动浏览器去打开目标地址；如果是 query 或 hash 场景，会读取浏览器渲染后的页面结果；如果是表单场景，也会通过浏览器侧提交表单，而不是只用 HTTP 客户端直接发 POST。这样它看到的是“浏览器最终渲染成了什么、脚本运行后发生了什么”。',
          '结果之所以会有出入，通常是因为页面里存在前端渲染、异步脚本、location.hash 处理、事件触发、前端路由或脚本拼接逻辑。不开启 Selenium 时，这些浏览器侧行为往往不会被完整复现；开启后，浏览器把这些逻辑跑起来，结果就更容易接近真实用户访问时看到的页面。',
          '哪个更准要分场景看：如果只是普通服务端回显、表单回显或静态响应检查，不开 Selenium 往往已经够用，而且更稳；如果页面强依赖 JavaScript、DOM 更新、hash 路由、动态渲染，开启 Selenium 通常更接近真实结果。',
          '因此最稳妥的理解方式是：不开 Selenium 更适合快速第一轮验证，开启 Selenium 更适合做更接近真实浏览器行为的补充确认。两者不是互相否定，而是适合不同验证层次。'
        ],
        bullets: [
          '不开 Selenium 更像“看响应文本”。',
          '开 Selenium 更像“看浏览器最终页面和脚本执行结果”。',
          '对前端驱动场景，Selenium 通常更接近真实结果。'
        ],
        tags: ['FAQ', 'Selenium', '动态验证', '浏览器验证'],
        resources: []
      },
      {
        id: 'faq_dynamic_no_trigger',
        q: '动态验证没触发，是不是就说明没有问题？',
        a: '不是。没触发只说明这一次验证没有看到明显信号，不代表风险路径一定不存在。',
        details: [
          '可能是 payload 不匹配、上下文不同、需要特定用户状态、页面脚本有时序要求，或者危险链路只在某些分支里出现。',
          '动态验证的价值在于补充证据，而不是替代全部人工判断。',
          '如果静态证据仍然很强，动态没触发也依然值得继续复核。'
        ],
        bullets: [
          '动态验证阴性 != 绝对安全',
          '静态证据强时，仍要继续看源码和页面行为'
        ],
        tags: ['FAQ', '动态验证', '复核'],
        resources: []
      },
      {
        id: 'faq_ai_payload_generation',
        q: 'AI 生成 Payload 和系统内置 Payload 有什么区别？',
        a: '系统内置 Payload 是固定预设的通用探针和利用串，AI 生成 Payload 则会结合当前页面的具体漏洞上下文来定制。',
        details: [
          '内置 payload 覆盖的是最常见的几类场景，例如标签注入、属性逃逸、字符串闭合等，但它们不会考虑某个具体页面的数据流路径、sink 类型或回显位置。',
          'AI 生成 Payload 会读取当前页面的静态分析结果（如 AST 数据流中的 source、sink、flow_display），并结合页面 HTML 片段和回显上下文来设计更有针对性的 payload。',
          '例如，如果分析发现 location.search 的值最终流入 innerHTML，AI 可能会生成更贴合该路径的 payload，而不是简单复用通用标签注入。',
          'AI 生成 Payload 提供两种模式：安全探针模式只生成非执行标记，适合第一轮确认链路；利用验证模式生成真实 XSS payload，适合深入验证。'
        ],
        bullets: [
          '内置 payload 是通用覆盖，AI payload 是上下文定制。',
          'AI payload 更贴合具体数据流，但不一定每次都比通用 payload 更有效。',
          '探针模式适合安全优先的验证，利用模式适合深度验证。'
        ],
        tags: ['FAQ', 'AI Payload', '生成', '上下文'],
        resources: []
      }
    ]
  }
]
