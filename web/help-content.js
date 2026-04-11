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
          'query 来自 URL 查询参数，最常见，也最容易与反射型或 DOM 型处理逻辑结合。',
          'form 来自表单字段，适合测试页面提交、回显、客户端拼接逻辑。',
          'hash 来自 location.hash，常用于前端路由、片段定位和纯浏览器端 DOM 处理。'
        ],
        bullets: [
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
          { label: 'MDN: Node.textContent', href: 'https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent' },
          { label: 'MDN: EventTarget.addEventListener', href: 'https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener' }
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
          { label: 'MDN: Content Security Policy', href: 'https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP' }
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
      }
    ]
  }
]
