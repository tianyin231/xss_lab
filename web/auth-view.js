export const AUTH_TEMPLATE = `
  <div class="authShell">
    <section class="authCard">
      <div class="authBrand">
        <div class="authEyebrow">XSSLab</div>
        <h1 class="authTitle">{{ authMode === 'login' ? '登录系统' : '注册账号' }}</h1>
        <p class="authText">
          {{ authMode === 'login'
            ? '登录后即可访问任务面板、工作台和 AI 分析功能。'
            : '使用用户名、密码和注册口令创建本地账号。' }}
        </p>
      </div>

      <div class="authField">
        <label class="label">API</label>
        <input class="input" v-model="apiBase" placeholder="http://127.0.0.1:5001/api" />
      </div>

      <div class="authField">
        <label class="label">用户名</label>
        <input class="input" v-model="authForm.username" placeholder="请输入用户名" />
      </div>

      <div class="authField">
        <label class="label">密码</label>
        <input class="input" v-model="authForm.password" type="password" placeholder="请输入密码" />
      </div>

      <div class="authField" v-if="authMode === 'register'">
        <label class="label">显示名</label>
        <input class="input" v-model="authForm.display_name" placeholder="可选" />
      </div>

      <div class="authField" v-if="authMode === 'register'">
        <label class="label">注册口令</label>
        <input class="input" v-model="authForm.invite_code" placeholder="请输入注册口令" />
      </div>

      <div class="authError" v-if="authError">{{ authError }}</div>

      <button class="btn authSubmitBtn" :disabled="authLoading" @click="submitAuth()">
        {{ authLoading ? '提交中...' : (authMode === 'login' ? '登录' : '注册并登录') }}
      </button>

      <button class="authSwitchBtn" :disabled="authLoading" @click="toggleAuthMode()">
        {{ authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
      </button>
    </section>
  </div>
`
