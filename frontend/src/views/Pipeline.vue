<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePipelineStore } from '../stores/pipeline'
import { api } from '../api/http'

const route = useRoute()
const router = useRouter()
const store = usePipelineStore()

// Step 1 state
const platforms = ref<any[]>([])
const platformSearch = ref('')
const folder = ref('')
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)

const localPathInput = ref('')
const wmPlan = ref<any[]>([])
const wmSkipped = ref<any[]>([])

// 正在展开编辑的平台 ID（null = 无）
const wmEditingId = ref<number | null>(null)

function wmPositionLabel(pos: string): string {
  const map: Record<string, string> = {
    'bottom-right': '右下角', 'bottom-left': '左下角',
    'top-right': '右上角', 'top-left': '左上角', 'center': '居中',
  }
  return map[pos] || pos || '右下角'
}

function toggleWmEdit(pid: number) {
  wmEditingId.value = wmEditingId.value === pid ? null : pid
}

// 水印状态中文映射
function wmStatusLabel(status: string): string {
  const map: Record<string, string> = { pending: '等待中', running: '处理中', done: '✅ 完成', failed: '失败', skipped: '已跳过' }
  return map[status] || status
}
function wmModeLabel(mode: string): string {
  const map: Record<string, string> = { 'corner-cycle': '四角轮转', 'fixed': '固定位置', 'dual-diagonal': '双水印对角' }
  return map[mode] || mode || '—'
}

// 水印是否全部完成
const wmAllDone = computed(() => {
  const entries = Object.values(store.wmProgress)
  return entries.length > 0 && entries.every(p => p.status === 'done' || p.status === 'skipped')
})

// 水印完成文字（如 "图片 ×6 水印已添加"）
function wmDoneText(info: { images_count?: number; videos_count?: number }): string {
  const parts: string[] = []
  if (info.images_count) parts.push(`图片 ×${info.images_count}`)
  if (info.videos_count) parts.push(`视频 ×${info.videos_count}`)
  return parts.length > 0 ? `${parts.join(' + ')} 水印已添加` : '水印处理完成'
}

// 平台 ID → 名称映射（从平台列表构建）
const platformNameMap = computed(() => {
  const map: Record<number, string> = {}
  for (const p of platforms.value) {
    map[p.id] = p.name
  }
  return map
})

/** 发布阶段中文映射 */
const phaseLabel: Record<string, string> = {
  login: '登录中',
  upload_cover: '上传封面',
  upload_images: '上传图片',
  upload_video: '上传视频',
  slicing: '视频切片中',
  slicing_retry: '切片重试中',
  slice_pending: '切片待确认',
  building: '组装正文',
  publishing: '发布帖子',
}

async function retryPlatform(platformId: number, skipVideo: boolean = false) {
  if (!store.taskId) return
  try {
    await api('POST', `/pipeline/${store.taskId}/step/6/retry`, { platform_id: platformId, skip_video: skipVideo })
  } catch (e: any) {
    const detail = e.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : JSON.stringify(detail) || '重试失败'
    alert(msg)
  }
}

// 封面图片 URL 转换
function coverUrl(path: string): string {
  // 绝对路径（readytopublish 目录下的封面）→ 通过 preview API 访问
  if (path.startsWith('/') && !path.startsWith('/uploads/') && !path.startsWith('/app/')) {
    return `/api/pipeline/${store.taskId}/preview?path=${encodeURIComponent(path)}`
  }
  // Docker 容器路径
  if (path.startsWith('/app/backend/uploads/')) {
    return path.replace('/app/backend/uploads/', '/uploads/')
  }
  if (path.startsWith('/uploads/')) return path
  // 相对路径
  return `/uploads/${path}`
}

// Step 2 state
const copyForm = ref({ protagonist: '', event: '', photos: '', video_desc: '', style: '反转打脸风', author: '编辑', categories: [] as string[], title_range: '28', kw_count: 10, body_len: 400 })
const editTitle = ref('')
const editKeywords = ref('')
const editBody = ref('')
const layoutPreset = ref('img-interleave')
const layoutTemplate = ref('正文\n图片1-3\n\n## 小标题\n正文\n图片4-6\n\n## 小标题\n正文\n视频')

// Multi-platform edit state
const currentPlatformTab = ref<number | null>(null)
const platformEdits = ref<Record<number, { title: string; keywords: string; body: string; author: string; categories: string[] }>>({})
const hasMultiPlatformResults = computed(() => Object.keys(store.copyResults).length > 1)

function switchPlatformTab(pid: number) {
  // Save current tab's edit state
  if (currentPlatformTab.value !== null) {
    platformEdits.value[currentPlatformTab.value] = {
      title: editTitle.value, keywords: editKeywords.value, body: editBody.value,
      author: platformEdits.value[currentPlatformTab.value]?.author || copyForm.value.author,
      categories: platformEdits.value[currentPlatformTab.value]?.categories || [],
    }
  }
  currentPlatformTab.value = pid
  // Load the new tab's data
  const edit = platformEdits.value[pid]
  if (edit) {
    editTitle.value = edit.title
    editKeywords.value = edit.keywords
    editBody.value = edit.body
  }
}

function addPlatformCategory(cat: string, pid: number) {
  if (!platformEdits.value[pid]) return
  const cats = platformEdits.value[pid].categories
  if (!cats.includes(cat)) cats.push(cat)
}
function removePlatformCategory(cat: string, pid: number) {
  if (!platformEdits.value[pid]) return
  platformEdits.value[pid].categories = platformEdits.value[pid].categories.filter(c => c !== cat)
}

const LAYOUT_PRESETS: Record<string, string> = {
  'img-interleave': '正文\n图片1-3\n\n## 小标题\n正文\n图片4-6\n\n## 小标题\n正文\n视频',
  'vid-list': '正文\n图片1-3\n\n## 小标题\n视频1\n\n## 小标题\n视频2\n\n## 小标题\n视频3',
  'mixed': '正文\n图片1-3\n\n## 小标题\n正文\n视频1\n\n## 小标题\n正文\n图片4-6\n视频2',
}
function onLayoutPresetChange() {
  if (layoutPreset.value && layoutPreset.value !== 'custom') {
    layoutTemplate.value = LAYOUT_PRESETS[layoutPreset.value] || ''
  } else if (layoutPreset.value === 'custom') {
    layoutTemplate.value = ''
  }
}


// Step 3 state
const prefix = ref('')
const startNum = ref(1)
const separator = ref('_')

// Step 4 state
const coverLayout = ref('triple')
const coverSize = ref('1300x640')
const coverHeadroom = ref(15)
const coverTab = ref(0)  // 当前选中的平台标签索引
const platformCoverConfigs = ref<Record<number, { layout: string; size: string; headroom: number }>>({})

// 获取当前平台的封面配置（lazy init）
function getPlatformCoverConfig(pid: number) {
  if (!platformCoverConfigs.value[pid]) {
    platformCoverConfigs.value[pid] = { layout: 'triple', size: '1300x640', headroom: 15 }
  }
  return platformCoverConfigs.value[pid]
}

const isMultiPlatform = computed(() => store.selectedPlatforms.length > 1)

// 将 selectedPlatforms (number[]) 映射为带 name 的对象数组
const selectedPlatformList = computed(() =>
  store.selectedPlatforms.map(id => ({ id, name: platformNameMap.value[id] || `平台 ${id}` }))
)

const stepNames = ['素材 & 平台', '文案生成', '图片重命名', '封面制作', '水印处理', '上传 & 发布']

// 按部组分组
const groupedPlatforms = computed(() => {
  const groups: Record<string, any[]> = {}
  const q = platformSearch.value.toLowerCase()
  for (const p of platforms.value) {
    if (q && !p.name.toLowerCase().includes(q) && !p.dept.includes(q)) continue
    if (!groups[p.dept]) groups[p.dept] = []
    groups[p.dept].push(p)
  }
  return groups
})

const selectedSet = computed(() => new Set(store.selectedPlatforms))

function togglePlatform(id: number) {
  const idx = store.selectedPlatforms.indexOf(id)
  if (idx >= 0) store.selectedPlatforms.splice(idx, 1)
  else store.selectedPlatforms.push(id)
}

function selectAllGroup(dept: string) {
  const ids = (groupedPlatforms.value[dept] || []).map((p: any) => p.id)
  const allSelected = ids.every((id: number) => selectedSet.value.has(id))
  for (const id of ids) {
    const idx = store.selectedPlatforms.indexOf(id)
    if (allSelected && idx >= 0) store.selectedPlatforms.splice(idx, 1)
    else if (!allSelected && idx < 0) store.selectedPlatforms.push(id)
  }
}

// 拖拽上传
function onDragOver(e: DragEvent) { e.preventDefault(); isDragging.value = true }
function onDragLeave() { isDragging.value = false }

async function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const items = e.dataTransfer?.items
  if (!items) return
  const files: File[] = []
  for (let i = 0; i < items.length; i++) {
    const entry = items[i].webkitGetAsEntry?.()
    if (entry) {
      await collectFiles(entry, files)
    } else {
      const f = items[i].getAsFile()
      if (f) files.push(f)
    }
  }
  if (files.length) await store.uploadFiles(files)
}

async function collectFiles(entry: any, files: File[]): Promise<void> {
  if (entry.isFile) {
    const f: File = await new Promise(r => entry.file(r))
    files.push(f)
  } else if (entry.isDirectory) {
    const reader = entry.createReader()
    const entries: any[] = await new Promise(r => reader.readEntries(r))
    for (const e of entries) await collectFiles(e, files)
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    store.uploadFiles(Array.from(input.files))
    input.value = ''
  }
}

function triggerUploadFolder() {
  folderInput.value?.click()
}
function triggerUploadFiles() {
  fileInput.value?.click()
}

async function handleLocalPath() {
  const path = localPathInput.value.trim()
  if (!path) return
  try {
    await store.useLocalPath(path)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '路径加载失败')
  }
}

// Step navigation
function canNext(): boolean {
  if (store.currentStep === 0) return store.selectedPlatforms.length > 0 && store.fileManifest.images.length + store.fileManifest.videos.length > 0
  if (store.currentStep === 1) return !!editTitle.value
  return true
}

// 自动推进：素材+平台就绪后自动进入文案步骤
const step0Ready = computed(() =>
  store.currentStep === 0 &&
  store.selectedPlatforms.length > 0 &&
  store.fileManifest.images.length + store.fileManifest.videos.length > 0
)
let autoAdvanceTimer: ReturnType<typeof setTimeout> | null = null
watch(step0Ready, (ready) => {
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null }
  if (ready) {
    autoAdvanceTimer = setTimeout(() => {
      if (step0Ready.value && !isSubmitting.value) handleNext()
    }, 800)
  }
})

// Loading guards for confirm buttons (r2-20 double-click prevention)
const isSubmitting = ref(false)

async function handleNext() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    if (store.currentStep === 0) {
      await store.createTask(store.folderPath, store.selectedPlatforms)
      await store.loadCategories()
      // 自动从 TXT 提取内容填充文案表单
      autoFillFromTxt()
    }
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '操作失败')
  } finally {
    isSubmitting.value = false
  }
}

/** 从上传的 TXT 文件内容自动填充文案输入 */
function autoFillFromTxt() {
  const contents = store.fileManifest.txt_contents
  if (!contents || Object.keys(contents).length === 0) return

  // 合并所有 TXT 内容
  const allText = Object.values(contents).join('\n\n').trim()
  if (!allText) return

  // 尝试解析结构化内容（标题:xxx 主角:xxx 等）
  const lines = allText.split('\n').map(l => l.trim()).filter(Boolean)

  let protagonist = ''
  let event = ''
  let photos = ''
  let videoDesc = ''
  let body = ''
  const bodyLines: string[] = []

  for (const line of lines) {
    const lower = line.toLowerCase()
    // 匹配 "主角：xxx" 或 "主角:xxx" 格式
    const kv = line.match(/^(主角|角色|人物|protagonist)[：:]\s*(.+)/i)
    if (kv) { protagonist = kv[2].trim(); continue }

    const ev = line.match(/^(事件|事情|描述|event)[：:]\s*(.+)/i)
    if (ev) { event = ev[2].trim(); continue }

    const ph = line.match(/^(照片|图片|photos?)[：:]\s*(.+)/i)
    if (ph) { photos = ph[2].trim(); continue }

    const vd = line.match(/^(视频|video)[：:]\s*(.+)/i)
    if (vd) { videoDesc = vd[2].trim(); continue }

    // 其他行视为正文补充
    bodyLines.push(line)
  }

  // 如果没有结构化字段，把整段内容当事件描述
  if (!protagonist && !event && bodyLines.length > 0) {
    // 第一行当主角，第二行当事件，剩下当补充
    if (bodyLines.length >= 2) {
      protagonist = bodyLines[0]
      event = bodyLines[1]
    } else {
      event = bodyLines[0]
    }
  }

  // 填充表单（只填空的字段，不覆盖用户已填内容）
  if (protagonist && !copyForm.value.protagonist) copyForm.value.protagonist = protagonist
  if (event && !copyForm.value.event) copyForm.value.event = event
  if (photos && !copyForm.value.photos) copyForm.value.photos = photos
  if (videoDesc && !copyForm.value.video_desc) copyForm.value.video_desc = videoDesc

  // 图片/视频数量自动填充
  if (!copyForm.value.photos && store.fileManifest.images.length > 0) {
    copyForm.value.photos = `${store.fileManifest.images.length}张图片`
  }
  if (!copyForm.value.video_desc && store.fileManifest.videos.length > 0) {
    copyForm.value.video_desc = `${store.fileManifest.videos.length}段视频`
  }
}

// 返回上一步（各步数据保留，不清除）
async function handlePrev() {
  if (store.currentStep <= 0) return
  store.currentStep = store.currentStep - 1
  // 返回封面步时，若 store 中无封面候选则从服务端补载
  if (store.currentStep === 3 && !store.coverCandidates.length && store.taskId) {
    try {
      await store.loadTask(store.taskId, false)
    } catch {}
  }
  // 返回水印步时，清空旧进度以显示方案预览
  if (store.currentStep === 4) {
    store.wmProgress = {}
  }
}

// Step 3 重命名预览 — 本地实时计算
const renamePreviewLocal = computed(() => {
  const images = store.fileManifest.images
  if (!images.length || !prefix.value) return []
  const digits = String(images.length + startNum.value - 1).length
  return images.map((f: string, i: number) => {
    const num = String(startNum.value + i).padStart(digits, '0')
    const ext = f.substring(f.lastIndexOf('.'))
    return { old: f, new: `${prefix.value}${separator.value}${num}${ext}` }
  })
})

// Step 6 发布按钮是否可用
const canPublish = computed(() => {
  // 只要在 Step 6 且有选中的平台就可以发布
  if (store.currentStep !== 5) return false
  // 有 publishStatus 数据时，检查是否还有未发布的
  const statuses = Object.values(store.publishStatus)
  if (statuses.length > 0) {
    return statuses.some((s: any) => s.status !== 'published' && s.status !== 'publishing')
  }
  // 没有 publishStatus 但有选中平台，也允许发布
  return store.selectedPlatforms.length > 0
})

async function handleGenerateCopy() {
  if (!copyForm.value.protagonist.trim()) {
    alert('请填写主角')
    return
  }
  if (!copyForm.value.event.trim()) {
    alert('请填写事件')
    return
  }
  try {
    await store.generateCopy(copyForm.value)
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message || '文案生成请求失败'
    alert(typeof msg === 'string' ? msg : JSON.stringify(msg))
    store.isGenerating = false
  }
}

async function handleConfirmCopy() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    // Save current tab's edits first
    if (hasMultiPlatformResults.value && currentPlatformTab.value !== null) {
      platformEdits.value[currentPlatformTab.value] = {
        title: editTitle.value, keywords: editKeywords.value, body: editBody.value,
        author: platformEdits.value[currentPlatformTab.value]?.author || copyForm.value.author,
        categories: platformEdits.value[currentPlatformTab.value]?.categories || [],
      }
    }

    if (hasMultiPlatformResults.value && Object.keys(platformEdits.value).length > 0) {
      // Multi-platform: collect all platform copies
      const platformCopies = Object.entries(platformEdits.value).map(([pid, edit]) => ({
        platform_id: Number(pid),
        title: edit.title, keywords: edit.keywords, body: edit.body,
        author: edit.author, categories: edit.categories,
      }))
      const first = platformCopies[0]
      await store.confirmCopy(
        first.title, first.keywords, first.body, first.author, first.categories,
        layoutTemplate.value, platformCopies,
      )
    } else {
      // Single platform: original behavior
      await store.confirmCopy(editTitle.value, editKeywords.value, editBody.value, copyForm.value.author, copyForm.value.categories, layoutTemplate.value)
    }

    // 半自动：自动生成重命名前缀并立即执行重命名
    const autoPrefix = (copyForm.value.protagonist + '_' + copyForm.value.event).slice(0, 30)
    prefix.value = autoPrefix
    await store.confirmRename(autoPrefix, 1, 2, '_')
    // 后端 advance_step(2,3) 会通过 WS 推送 to_step:3 自动切换到封面步骤
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '确认文案失败')
  } finally {
    isSubmitting.value = false
  }
}

async function handleConfirmRename() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    await store.confirmRename(prefix.value, startNum.value, 2, separator.value)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '确认重命名失败')
  } finally {
    isSubmitting.value = false
  }
}

const isGeneratingCover = ref(false)
let coverPollTimer: number | null = null

async function handleGenerateCover() {
  isGeneratingCover.value = true
  store.coverCandidates = []
  try {
    if (isMultiPlatform.value) {
      // 多平台：每个平台独立生成封面
      const configs = selectedPlatformList.value.map(p => {
        const cfg = getPlatformCoverConfig(p.id)
        return {
          platform_id: p.id,
          platform_name: p.name,
          layout: cfg.layout,
          head_margin: cfg.headroom,
          size: cfg.size,
        }
      })
      await store.generateCover(coverLayout.value, 1, coverHeadroom.value, coverSize.value, configs)
    } else {
      await store.generateCover(coverLayout.value, 3, coverHeadroom.value, coverSize.value)
    }
    // WS 的 step_changed 事件会自动触发 loadTask 刷新封面数据
    // 这里只设置超时保护，不再轮询 API（避免与 WS 推送重复请求）
    if (coverPollTimer) clearInterval(coverPollTimer)
    coverPollTimer = window.setTimeout(async () => {
      // 60 秒超时保护：如果 WS 没推送结果，回退到一次性 API 查询
      if (!isGeneratingCover.value) return
      try {
        const data = await api('GET', `/pipeline/${store.taskId}`)
        const step3 = (data.steps || []).find((s: any) => s.step === 3)
        if (step3 && (step3.status === 'awaiting_confirm' || step3.status === 'done')) {
          isGeneratingCover.value = false
          let stepData = step3.data
          if (typeof stepData === 'string') try { stepData = JSON.parse(stepData) } catch {}
          if (stepData?.candidates) store.coverCandidates = stepData.candidates
          await store.loadTask(store.taskId!, false)
        } else if (step3?.status === 'failed') {
          isGeneratingCover.value = false
          alert('封面生成失败: ' + (step3.error || '未知错误'))
        }
      } catch {}
      coverPollTimer = null
    }, 60000) as unknown as number
  } catch (e: any) {
    isGeneratingCover.value = false
    const detail = e.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ') : '封面生成失败'
    alert(msg)
  }
}

const showImagePicker = ref(false)
const pickerSelectedImages = ref<string[]>([])

function openImagePicker() {
  pickerSelectedImages.value = []
  showImagePicker.value = true
}

function togglePickerImage(img: string) {
  const idx = pickerSelectedImages.value.indexOf(img)
  if (idx >= 0) pickerSelectedImages.value.splice(idx, 1)
  else pickerSelectedImages.value.push(img)
}

async function confirmPickerImages() {
  if (!pickerSelectedImages.value.length || !store.taskId) return
  // 用选中的图片生成封面
  try {
    await api('POST', `/pipeline/${store.taskId}/step/4/generate`, {
      layout: coverLayout.value,
      candidates: 1,
      head_margin: coverHeadroom.value,
      selected_images: pickerSelectedImages.value,
    })
    showImagePicker.value = false
    isGeneratingCover.value = true
    // 复用封面轮询
    handleGenerateCover()
  } catch (e: any) {
    alert(e.response?.data?.detail || '生成失败')
  }
}

async function handleConfirmCover() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    if (isMultiPlatform.value && Object.keys(store.platformCovers).length > 0) {
      // 多平台：传递各平台独立封面路径
      await store.confirmCover(0, store.platformCovers)
    } else {
      await store.confirmCover(store.selectedCover)
    }
    store.saveDraft()

    // 触发水印处理（后端异步执行，水印完成后自动发布）
    await store.confirmWatermark([])

    // 水印+上传+发布全部在后台队列执行，直接开始新任务
    handleNewTask()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '确认封面失败')
  } finally {
    isSubmitting.value = false
  }
}

async function handleConfirmWatermark() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    // 将本地编辑过的水印参数作为 overrides 传给后端
    const overrides = wmPlan.value.map(p => ({
      platform_id: p.platform_id,
      img_wm_position: p.wm_position || p.img_wm_position,
      img_wm_width: p.wm_width || p.img_wm_width,
      vid_wm_mode: p.vid_wm_mode,
      vid_wm_scale: p.vid_wm_scale,
    }))
    await store.confirmWatermark(overrides)
    // 轮询等待水印处理完成（WebSocket 会推送进度，这里做超时保护）
    const pollWm = setInterval(async () => {
      if (!store.taskId) { clearInterval(pollWm); return }
      try {
        await store.loadTask(store.taskId, false)
        // 水印全部完成或进入下一步时停止轮询
        const allWmDone = Object.values(store.wmProgress).length > 0 &&
          Object.values(store.wmProgress).every(p => p.status === 'done' || p.status === 'skipped' || p.status === 'failed')
        if (allWmDone || store.currentStep >= 5) {
          clearInterval(pollWm)
        }
      } catch {}
    }, 3000)
    // 120秒后无论如何停止轮询（视频水印可能较慢）
    setTimeout(() => clearInterval(pollWm), 120000)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '确认水印失败')
  } finally {
    isSubmitting.value = false
  }
}

async function handleWmDone() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    await store.confirmWatermarkDone()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '确认失败')
  } finally {
    isSubmitting.value = false
  }
}

async function handlePublish() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    await store.publish()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    alert(typeof detail === 'string' ? detail : JSON.stringify(detail) || e.message || '发布失败')
  } finally {
    isSubmitting.value = false
  }
}

// 监听文案生成结果
watch(() => store.copyResult, (r) => {
  if (r) {
    editTitle.value = r.title
    editKeywords.value = r.keywords
    editBody.value = r.body
    // AI 返回的分类自动选中
    if (r.category) {
      copyForm.value.categories = r.category.split(',').map(c => c.trim()).filter(Boolean)
    }
    // 分类为空时，从分类库自动选择（今日吃瓜 + 第一个非今日吃瓜的）
    if (copyForm.value.categories.length === 0 && store.dynamicCategories.length > 0) {
      const allCats = store.dynamicCategories
      if (allCats.length <= 2) {
        copyForm.value.categories = [...allCats]
      } else {
        const mustHave = allCats.find(c => c === '今日吃瓜')
        const second = allCats.find(c => c !== '今日吃瓜')
        copyForm.value.categories = [mustHave, second].filter(Boolean) as string[]
      }
    }
  }
})

watch(() => store.copyResults, (results) => {
  if (results && Object.keys(results).length > 0) {
    platformEdits.value = {}
    let first = true
    for (const [pid, r] of Object.entries(results) as any) {
      const numPid = Number(pid)
      let cats = r.categories || []
      // 分类为空时，从平台分类库自动选择（今日吃瓜 + 第一个非今日吃瓜的）
      if (cats.length === 0) {
        const platCats = store.perPlatformCategories[numPid]?.categories || []
        if (platCats.length <= 2) {
          cats = [...platCats]
        } else {
          const mustHave = platCats.find((c: string) => c === '今日吃瓜')
          const second = platCats.find((c: string) => c !== '今日吃瓜')
          cats = [mustHave, second].filter(Boolean) as string[]
        }
      }
      platformEdits.value[numPid] = {
        title: r.title || '', keywords: r.keywords || '', body: r.body || '',
        author: r.author || copyForm.value.author, categories: cats,
      }
      if (first) {
        currentPlatformTab.value = numPid
        editTitle.value = r.title || ''
        editKeywords.value = r.keywords || ''
        editBody.value = r.body || ''
        first = false
      }
    }
  }
}, { deep: true })

// 监听封面候选变化 — WS 推送后 store 刷新会触发这里
watch(() => store.coverCandidates, (candidates) => {
  if (candidates && candidates.length > 0 && isGeneratingCover.value) {
    isGeneratingCover.value = false
    if (coverPollTimer) { clearTimeout(coverPollTimer); coverPollTimer = null }
  }
})

// 监听步骤变化，加载对应数据
watch(() => store.currentStep, async (step) => {
  // 进入 Step 6 时，确保 publishStatus 有数据
  if (step === 5 && store.taskId) {
    if (Object.keys(store.publishStatus).length === 0) {
      // 从任务数据初始化 publishStatus
      await store.loadTask(store.taskId)
    }
  }
  // 进入 Step 5 时加载水印方案预览
  if (step === 4 && store.taskId) {
    try {
      const plan = await api('GET', `/pipeline/${store.taskId}/step/5/plan`)
      wmPlan.value = plan.platforms || []
      wmSkipped.value = plan.skipped || []
    } catch { wmPlan.value = []; wmSkipped.value = [] }
  }
})

const hasDraft = ref(false)

onMounted(async () => {
  // 加载平台列表
  try { platforms.value = await api('GET', '/platforms') } catch {}

  // 如果有 ID 参数，加载已有任务
  const id = route.params.id
  if (id) {
    await store.loadTask(Number(id))
    if (store.copyResult) {
      editTitle.value = store.copyResult.title
      editKeywords.value = store.copyResult.keywords
      editBody.value = store.copyResult.body
    }
    prefix.value = store.renamePrefix
    folder.value = store.folderPath
  } else {
    // 尝试恢复草稿
    if (await store.loadDraft()) {
      hasDraft.value = true
      if (store.copyResult) {
        editTitle.value = store.copyResult.title
        editKeywords.value = store.copyResult.keywords
        editBody.value = store.copyResult.body
      }
      prefix.value = store.renamePrefix
      folder.value = store.folderPath
    } else {
      store.reset()
    }
    // 获取预估任务编号（新建时显示）
    if (!store.taskNo) {
      try {
        const res = await api('GET', '/pipeline/next-no')
        store.taskNo = res.task_no
      } catch {}
    }
  }
})

onUnmounted(() => {
  // 清理定时器和 WebSocket 连接
  if (coverPollTimer) { clearTimeout(coverPollTimer); coverPollTimer = null }
  store.cleanup()
})

function handleSaveDraft() {
  store.saveDraft()
  alert('草稿已保存')
}

function handleDiscardDraft() {
  store.clearDraft()
  store.reset()
  hasDraft.value = false
}

function handleNewTask() {
  store.clearDraft()
  store.reset()
  folder.value = ''
  editTitle.value = ''
  editKeywords.value = ''
  editBody.value = ''
  // 如果当前在 /pipeline/:id，跳到 /pipeline
  if (route.params.id) {
    router.push({ name: 'pipeline' })
  }
}
</script>

<template>
  <div>
    <div class="wizard-wrap">
      <!-- Header -->
      <div style="padding:20px 24px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px">
          <h3 style="font-size:16px;font-weight:700">
            {{ store.taskId ? '发帖任务' : '新建发帖任务' }}
            <span style="color:var(--primary)">{{ store.taskNo || '' }}</span>
          </h3>
          <span v-if="store.taskId" style="font-size:11px;color:var(--t3);background:var(--bg4);padding:2px 8px;border-radius:4px">
            ID:{{ store.taskId }}
          </span>
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <span class="badge badge-primary" style="font-size:10px">● 流水线模式</span>
          <button class="btn btn-ghost btn-sm" @click="handleSaveDraft">💾 保存草稿</button>
        </div>
      </div>
      <!-- 草稿恢复提示 -->
      <div v-if="hasDraft && !store.taskId" style="padding:10px 24px;background:rgba(255,183,77,.08);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between">
        <span style="font-size:12px;color:var(--orange)">📋 已恢复上次未完成的草稿</span>
        <button class="btn btn-sm" style="color:var(--red);font-size:11px" @click="handleDiscardDraft">丢弃草稿</button>
      </div>

      <!-- Step indicators -->
      <div style="display:flex;align-items:center;padding:18px 24px;border-bottom:1px solid var(--bd);overflow-x:auto">
        <template v-for="(name, i) in stepNames" :key="i">
          <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
            <div :style="{
              width:'30px',height:'30px',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',
              fontSize:'13px',fontWeight:700,border:'2px solid',flexShrink:0,
              ...(i < store.currentStep ? {background:'var(--green-dim)',color:'var(--green)',borderColor:'var(--green)'}
                : i === store.currentStep ? {background:'var(--primary)',color:'#000',borderColor:'var(--primary)'}
                : {background:'var(--bg4)',color:'var(--t3)',borderColor:'var(--bd)'}),
            }">{{ i + 1 }}</div>
            <span :style="{fontSize:'12px',color: i<store.currentStep?'var(--green)':i===store.currentStep?'var(--t1)':'var(--t3)',fontWeight:i===store.currentStep?600:400}">{{ name }}</span>
          </div>
          <div v-if="i < 5" :style="{flex:1,height:'2px',minWidth:'20px',maxWidth:'50px',margin:'0 8px',background:i<store.currentStep?'var(--green)':'var(--bd)'}" />
        </template>
      </div>

      <!-- Step panels -->
      <div style="padding:28px 24px;min-height:400px">

        <!-- Step 1: 素材 & 平台 -->
        <div v-if="store.currentStep === 0">
          <div style="display:flex;gap:20px;flex-wrap:wrap">
            <div style="flex:1;min-width:300px">
              <h4 style="margin-bottom:12px;font-size:14px">素材文件夹</h4>

              <!-- 拖拽上传区域 -->
              <div class="upload-zone"
                   :class="{ dragging: isDragging, uploaded: store.fileManifest.images.length > 0 || store.fileManifest.videos.length > 0 || store.fileManifest.txts.length > 0 }"
                   @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop">
                <input ref="fileInput" type="file" multiple accept="image/*,video/*,.txt,.mp4,.mov,.avi,.mkv" style="display:none" @change="onFileSelect" />
                <input ref="folderInput" type="file" webkitdirectory style="display:none" @change="onFileSelect" />

                <!-- 上传中 -->
                <template v-if="store.isUploading">
                  <div class="upload-icon">⏳</div>
                  <div class="upload-hint">上传中… {{ store.uploadProgress }}%</div>
                  <div class="progress-bar" style="margin-top:10px;height:6px;max-width:300px;margin-left:auto;margin-right:auto">
                    <div class="progress-fill" :style="{width: store.uploadProgress + '%', background: 'var(--primary)'}" />
                  </div>
                </template>

                <!-- 已上传，显示识别结果 -->
                <template v-else-if="store.fileManifest.images.length > 0 || store.fileManifest.videos.length > 0 || store.fileManifest.txts.length > 0">
                  <div style="width:100%;text-align:left">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                      <span style="font-size:20px">📂</span>
                      <span style="font-size:14px;font-weight:600;color:var(--green)">素材已就绪 ✅</span>
                      <div style="margin-left:auto;display:flex;gap:6px">
                        <button class="btn btn-ghost btn-sm" @click.stop="triggerUploadFiles()">📎 追加文件</button>
                        <button class="btn btn-ghost btn-sm" @click.stop="triggerUploadFolder()">📁 追加文件夹</button>
                      </div>
                    </div>
                    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px">
                      <div style="display:flex;align-items:center;gap:6px;font-size:13px">
                        <span>🖼️</span>
                        <span>图片 × <strong style="color:var(--primary)">{{ store.fileManifest.images.length }}</strong></span>
                        <span v-if="store.fileManifest.images.length > 0 && store.fileManifest.images.length <= 6" style="font-size:11px;color:var(--t3)">
                          ({{ store.fileManifest.images[0] }} ~ {{ store.fileManifest.images[store.fileManifest.images.length - 1] }})
                        </span>
                      </div>
                      <div style="display:flex;align-items:center;gap:6px;font-size:13px">
                        <span>🎬</span>
                        <span>视频 × <strong style="color:var(--primary)">{{ store.fileManifest.videos.length }}</strong></span>
                        <span v-if="store.fileManifest.videos.length > 0" style="font-size:11px;color:var(--t3)">
                          ({{ store.fileManifest.videos.join(', ') }})
                        </span>
                      </div>
                      <div style="display:flex;align-items:center;gap:6px;font-size:13px">
                        <span>📄</span>
                        <span>文案 × <strong :style="{color: store.fileManifest.txts.length ? 'var(--primary)' : 'var(--t3)'}">{{ store.fileManifest.txts.length }}</strong></span>
                        <span v-if="!store.fileManifest.txts.length" style="font-size:11px;color:var(--t3)">(未检测到 TXT)</span>
                      </div>
                    </div>
                    <!-- 文件名标签 -->
                    <div v-if="store.fileManifest.images.length > 0 && store.fileManifest.images.length <= 20" style="display:flex;flex-wrap:wrap;gap:4px">
                      <span v-for="f in store.fileManifest.images" :key="f" style="font-size:10px;padding:2px 6px;background:var(--bg4);border-radius:4px;color:var(--t2)">🖼️ {{ f }}</span>
                      <span v-for="f in store.fileManifest.videos" :key="f" style="font-size:10px;padding:2px 6px;background:var(--bg4);border-radius:4px;color:var(--orange)">🎬 {{ f }}</span>
                      <span v-for="f in store.fileManifest.txts" :key="f" style="font-size:10px;padding:2px 6px;background:var(--bg4);border-radius:4px;color:var(--green)">📄 {{ f }}</span>
                    </div>
                  </div>
                </template>

                <!-- 初始状态 -->
                <template v-else>
                  <div class="upload-icon">📁</div>
                  <div class="upload-hint">拖入素材文件夹</div>
                  <div class="upload-sub" style="margin-bottom:10px">支持：图片（JPG/PNG/WebP）、视频（MP4/MOV）、文案（TXT）</div>
                  <div style="display:flex;gap:8px;justify-content:center" @click.stop>
                    <button class="btn btn-primary btn-sm" @click="triggerUploadFolder()">📁 选择文件夹</button>
                    <button class="btn btn-ghost btn-sm" @click="triggerUploadFiles()">📎 选择文件</button>
                  </div>
                </template>
              </div>

              <!-- 本地路径输入（Docker 挂载目录，免上传） -->
              <div style="margin-top:10px">
                <div style="font-size:11px;color:var(--t3);margin-bottom:4px">或输入服务器本地路径（免上传，秒级加载）</div>
                <div style="display:flex;gap:8px">
                  <input v-model="localPathInput" class="form-input" style="flex:1"
                         placeholder="/mnt/素材/item_20260410/OmniPublish_V2/task1/task1" />
                  <button class="btn btn-ghost" style="white-space:nowrap" @click="handleLocalPath"
                          :disabled="!localPathInput.trim() || store.isUploading">
                    📂 加载
                  </button>
                </div>
              </div>

              <!-- 文件识别结果 -->
              <div v-if="store.fileManifest.images.length > 0 || store.fileManifest.videos.length > 0"
                   style="margin-top:10px;padding:12px 14px;background:var(--bg3);border:1px solid var(--bd);border-radius:8px;font-size:12px;color:var(--t2)">
                <div style="font-weight:600;color:var(--t1);margin-bottom:8px">📂 已识别文件：</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap">
                  <div style="display:flex;align-items:center;gap:6px">
                    <span>🖼️</span>
                    <span>图片 × <strong style="color:var(--primary)">{{ store.fileManifest.images.length }}</strong></span>
                  </div>
                  <div style="display:flex;align-items:center;gap:6px">
                    <span>🎬</span>
                    <span>视频 × <strong style="color:var(--primary)">{{ store.fileManifest.videos.length }}</strong></span>
                  </div>
                  <div style="display:flex;align-items:center;gap:6px">
                    <span>📄</span>
                    <span>文案 × <strong :style="{color: store.fileManifest.txts.length ? 'var(--primary)' : 'var(--t3)'}">{{ store.fileManifest.txts.length }}</strong></span>
                    <span v-if="!store.fileManifest.txts.length" style="color:var(--t3)">(未检测到 TXT)</span>
                  </div>
                </div>
                <!-- 文件列表 -->
                <div v-if="store.fileManifest.images.length <= 12" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">
                  <span v-for="f in store.fileManifest.images" :key="f" style="font-size:10px;padding:2px 6px;background:var(--bg4);border-radius:4px;color:var(--t3)">{{ f }}</span>
                </div>
                <div v-else style="margin-top:6px;font-size:11px;color:var(--t3)">
                  {{ store.fileManifest.images[0] }} ~ {{ store.fileManifest.images[store.fileManifest.images.length - 1] }}
                </div>
                <div v-if="store.fileManifest.videos.length" style="margin-top:4px;display:flex;flex-wrap:wrap;gap:4px">
                  <span v-for="f in store.fileManifest.videos" :key="f" style="font-size:10px;padding:2px 6px;background:var(--bg4);border-radius:4px;color:var(--orange)">{{ f }}</span>
                </div>
              </div>
            </div>
            <div style="flex:1.5;min-width:400px">
              <h4 style="margin-bottom:12px;font-size:14px">选择发布平台</h4>
              <input v-model="platformSearch" class="form-input" placeholder="搜索平台名称…" style="margin-bottom:10px" />
              <div v-for="(items, dept) in groupedPlatforms" :key="dept" style="margin-bottom:12px">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                  <span style="font-size:12px;font-weight:600;color:var(--t2)">{{ dept }}</span>
                  <button class="btn btn-sm" style="font-size:10px;padding:2px 8px;color:var(--primary);border:1px solid var(--primary)" @click="selectAllGroup(dept as string)">全选</button>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px">
                  <div v-for="p in items" :key="p.id"
                       style="display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--bg3);cursor:pointer;font-size:12px;transition:.15s"
                       :style="selectedSet.has(p.id) ? {borderColor:'var(--primary)',background:'var(--primary-dim)'} : {}"
                       @click="togglePlatform(p.id)">
                    <div style="width:16px;height:16px;border-radius:4px;border:2px solid var(--bd);display:flex;align-items:center;justify-content:center;font-size:10px;flex-shrink:0"
                         :style="selectedSet.has(p.id) ? {borderColor:'var(--primary)',background:'var(--primary)',color:'#000'} : {}">
                      {{ selectedSet.has(p.id) ? '✓' : '' }}
                    </div>
                    <span :style="{flex:1,color:selectedSet.has(p.id)?'var(--t1)':'var(--t2)'}">{{ p.name }}</span>
                    <span style="font-size:9px;color:var(--t3)">{{ p.dept }}</span>
                  </div>
                </div>
              </div>
              <div style="margin-top:10px;font-size:12px;color:var(--t2)">已选择 <strong style="color:var(--primary)">{{ store.selectedPlatforms.length }}</strong> 个平台</div>
            </div>
          </div>
        </div>

        <!-- Step 2: 文案生成 -->
        <div v-if="store.currentStep === 1">
          <!-- TXT 素材内容展示 -->
          <div v-if="store.fileManifest.txt_contents && Object.keys(store.fileManifest.txt_contents).length"
               style="margin-bottom:16px;padding:14px;background:var(--bg1);border:1px solid var(--primary);border-radius:8px">
            <div style="font-size:11px;color:var(--primary);font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px">
              📄 已从素材 TXT 提取内容（已自动填充到下方表单）
            </div>
            <div v-for="(content, fname) in store.fileManifest.txt_contents" :key="fname"
                 style="margin-bottom:8px">
              <div style="font-size:10px;color:var(--t3);margin-bottom:4px">{{ fname }}</div>
              <div style="font-size:12px;color:var(--t2);white-space:pre-wrap;max-height:120px;overflow-y:auto;line-height:1.6;padding:8px 10px;background:var(--bg3);border-radius:6px">{{ content }}</div>
            </div>
          </div>

          <div style="display:flex;gap:20px;flex-wrap:wrap">
            <div style="flex:1;min-width:280px">
              <h4 style="margin-bottom:12px;font-size:14px">文案输入</h4>
              <div style="display:flex;gap:14px;margin-bottom:14px">
                <div class="form-group" style="flex:1"><label>主角</label><input v-model="copyForm.protagonist" class="form-input" placeholder="主角名 / 描述" /></div>
                <div class="form-group" style="flex:1"><label>事件</label><input v-model="copyForm.event" class="form-input" placeholder="发生了什么事" /></div>
              </div>
              <div style="display:flex;gap:14px;margin-bottom:14px">
                <div class="form-group" style="flex:1"><label>生活照描述</label><input v-model="copyForm.photos" class="form-input" :placeholder="`${store.fileManifest.images.length}张图片`" /></div>
                <div class="form-group" style="flex:1"><label>视频内容描述</label><input v-model="copyForm.video_desc" class="form-input" :placeholder="`${store.fileManifest.videos.length}段视频`" /></div>
              </div>
              <div style="margin-bottom:14px">
                <div class="form-group" style="flex:1"><label>文风</label>
                  <select v-model="copyForm.style" class="form-select">
                    <option>反转打脸风</option><option>搞笑玩梗风</option><option>麻辣吐槽风</option><option>深情共情风</option><option>悬念揭秘风</option>
                  </select>
                </div>
              </div>
              <div style="display:flex;gap:14px;margin-bottom:14px">
                <div class="form-group" style="flex:1"><label>标题字数</label><input v-model="copyForm.title_range" class="form-input" placeholder="28-35" /></div>
                <div class="form-group" style="flex:1"><label>关键词数量</label><input v-model.number="copyForm.kw_count" type="number" class="form-input" min="3" max="30" /></div>
                <div class="form-group" style="flex:1"><label>正文字数</label><input v-model.number="copyForm.body_len" type="number" class="form-input" min="200" max="3000" /></div>
              </div>
              <button class="btn btn-primary"
                      :disabled="store.isGenerating || !copyForm.protagonist.trim() || !copyForm.event.trim()"
                      @click="handleGenerateCopy">
                {{ store.isGenerating ? '⏳ 生成中...' : '🤖 AI 生成文案' }}
              </button>
              <span v-if="!copyForm.protagonist.trim() || !copyForm.event.trim()" style="font-size:11px;color:var(--orange);margin-left:8px">
                ← 请先填写主角和事件
              </span>
            </div>
            <div style="flex:1;min-width:280px">
              <h4 style="margin-bottom:12px;font-size:14px">生成结果</h4>
              <div v-if="store.isGenerating" class="ai-loading-box">
                <div class="ai-loading-dots"><span /><span /><span /></div>
                <div class="ai-loading-title">AI 正在生成文案...</div>
                <div class="ai-loading-sub">通常需要 10~30 秒，请耐心等待</div>
              </div>
              <template v-else>
                <!-- 多平台标签页 -->
                <div v-if="hasMultiPlatformResults" style="display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap">
                  <button v-for="pid in Object.keys(platformEdits).map(Number)" :key="pid"
                          class="btn btn-sm"
                          :style="{
                            background: currentPlatformTab === pid ? 'var(--primary)' : 'var(--bg4)',
                            color: currentPlatformTab === pid ? '#000' : 'var(--t2)',
                            border: currentPlatformTab === pid ? '1px solid var(--primary)' : '1px solid var(--bd)',
                            fontWeight: currentPlatformTab === pid ? 600 : 400,
                            padding: '4px 12px', fontSize: '12px', borderRadius: '6px', cursor: 'pointer',
                          }"
                          @click="switchPlatformTab(pid)">
                    {{ platformNameMap[pid] || `平台 ${pid}` }}
                  </button>
                </div>

                <div class="form-group" style="margin-bottom:10px"><label>标题</label><input v-model="editTitle" class="form-input" /></div>
                <div class="form-group" style="margin-bottom:10px"><label>关键词</label><input v-model="editKeywords" class="form-input" /></div>
                <div class="form-group" style="margin-bottom:10px"><label>正文</label><textarea v-model="editBody" class="form-textarea" rows="8" /></div>

                <!-- 多平台独立编辑：作者和分类 -->
                <div v-if="hasMultiPlatformResults && currentPlatformTab !== null && platformEdits[currentPlatformTab]"
                     style="border-top:1px solid var(--bd);padding-top:10px;margin-top:6px;margin-bottom:10px">
                  <div style="display:flex;gap:14px;margin-bottom:10px">
                    <div class="form-group" style="flex:1">
                      <label>作者</label>
                      <input v-model="platformEdits[currentPlatformTab].author" class="form-input" />
                    </div>
                  </div>
                  <div class="form-group" style="margin-bottom:10px">
                    <label>分类 <span style="font-size:10px;color:var(--t3)">({{ platformNameMap[currentPlatformTab] || '' }} 的分类库)</span></label>
                    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
                      <span v-for="c in platformEdits[currentPlatformTab].categories" :key="c"
                            style="padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer;background:var(--primary-dim);color:var(--primary);border:1px solid var(--primary);display:flex;align-items:center;gap:4px"
                            @click="removePlatformCategory(c, currentPlatformTab)">
                        {{ c }} <span style="font-size:13px">&times;</span>
                      </span>
                    </div>
                    <div v-if="currentPlatformTab !== null && store.perPlatformCategories[currentPlatformTab]?.categories?.length"
                         style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">
                      <span v-for="c in (store.perPlatformCategories[currentPlatformTab!]?.categories || []).filter((c: string) => !(platformEdits[currentPlatformTab!]?.categories || []).includes(c))"
                            :key="c"
                            style="padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer;background:var(--bg4);color:var(--t2);border:1px solid var(--bd);transition:.15s"
                            @click="addPlatformCategory(c, currentPlatformTab!)">
                        + {{ c }}
                      </span>
                    </div>
                  </div>
                </div>

                <div style="border-top:1px solid var(--bd);padding-top:10px;margin-top:6px;margin-bottom:10px">
                  <div style="display:flex;gap:14px;align-items:flex-start">
                    <div class="form-group" style="flex:0 0 160px">
                      <label>排版预设</label>
                      <select v-model="layoutPreset" class="form-select" @change="onLayoutPresetChange">
                        <option value="img-interleave">图文交替型</option>
                        <option value="vid-list">视频列表型</option>
                        <option value="mixed">图文+视频混合</option>
                        <option value="custom">自定义</option>
                      </select>
                    </div>
                    <div v-if="layoutPreset" class="form-group" style="flex:1">
                      <label>排版模板（可自由编辑）</label>
                      <textarea v-model="layoutTemplate" class="form-textarea" rows="6" style="font-family:'SF Mono',monospace;font-size:11px" />
                      <div class="form-hint">正文=段落 | 图片1-3=第1~3张图 | 视频/视频1=视频 | ## 小标题=二级标题</div>
                    </div>
                  </div>
                </div>
                <div style="display:flex;gap:8px">
                  <button class="btn btn-green" :disabled="!editTitle" @click="handleConfirmCopy">✅ 确认文案，下一步 →</button>
                  <button class="btn btn-ghost" @click="handleGenerateCopy">🔄 重新生成</button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Step 3: 重命名（自动执行） -->
        <div v-if="store.currentStep === 2">
          <h4 style="margin-bottom:12px;font-size:14px">图片批量重命名</h4>
          <div style="padding:20px;background:var(--bg3);border-radius:8px;text-align:center">
            <div style="font-size:14px;color:var(--primary);margin-bottom:8px">⏳ 正在自动重命名...</div>
            <div style="font-size:12px;color:var(--t2)">前缀: <strong>{{ prefix || '(自动生成)' }}</strong></div>
            <div style="font-size:11px;color:var(--t3);margin-top:4px">重命名完成后将自动进入封面制作步骤</div>
          </div>
          <!-- 实时预览 -->
          <div v-if="renamePreviewLocal.length" class="panel" style="margin-top:14px">
            <div style="font-size:12px;font-weight:600;color:var(--t2);margin-bottom:10px">重命名结果</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px">
              <template v-for="r in renamePreviewLocal" :key="r.old">
                <div style="color:var(--t3)">{{ r.old }}</div>
                <div style="color:var(--green)">→ {{ r.new }}</div>
              </template>
            </div>
          </div>
        </div>

        <!-- Step 4: 封面 -->
        <div v-if="store.currentStep === 3">
          <h4 style="margin-bottom:12px;font-size:14px">封面制作</h4>
          <p style="font-size:12px;color:var(--t2);margin-bottom:14px">系统将自动从素材图片中生成封面。{{ isMultiPlatform ? '每个平台可独立选择拼接方式。' : '请选择满意的封面，或重新生成。' }}</p>

          <!-- 多平台：平台标签页 -->
          <div v-if="isMultiPlatform" style="margin-bottom:14px">
            <div style="display:flex;gap:4px;border-bottom:2px solid var(--bd);margin-bottom:14px">
              <button v-for="(p, i) in selectedPlatformList" :key="p.id"
                      style="padding:6px 16px;font-size:12px;border:none;cursor:pointer;border-radius:6px 6px 0 0;transition:.15s"
                      :style="coverTab === i ? {background:'var(--primary)',color:'#000',fontWeight:600} : {background:'var(--bg3)',color:'var(--t2)'}"
                      @click="coverTab = i">
                {{ p.name }}
              </button>
            </div>
            <!-- 当前平台的封面配置 -->
            <div v-for="(p, i) in selectedPlatformList" :key="p.id" v-show="coverTab === i">
              <div style="display:flex;gap:14px;margin-bottom:14px;flex-wrap:wrap">
                <div class="form-group" style="flex:1;min-width:160px">
                  <label>拼接方式</label>
                  <select :value="getPlatformCoverConfig(p.id).layout" @change="getPlatformCoverConfig(p.id).layout = ($event.target as HTMLSelectElement).value" class="form-select">
                    <option value="triple">三拼（3 张横向拼接）</option>
                    <option value="single">单图（单张裁剪）</option>
                    <option value="double">双拼</option>
                    <option value="wide">宽屏横版</option>
                    <option value="portrait">竖版</option>
                  </select>
                </div>
                <div class="form-group" style="flex:1;min-width:160px">
                  <label>封面尺寸</label>
                  <select :value="getPlatformCoverConfig(p.id).size" @change="getPlatformCoverConfig(p.id).size = ($event.target as HTMLSelectElement).value" class="form-select">
                    <option value="1300x640">1300 x 640（标准横版）</option>
                    <option value="800x450">800 x 450</option>
                    <option value="900x1200">900 x 1200（竖版）</option>
                  </select>
                </div>
                <div class="form-group" style="flex:0.5;min-width:100px">
                  <label>头顶留白 %</label>
                  <input :value="getPlatformCoverConfig(p.id).headroom" @input="getPlatformCoverConfig(p.id).headroom = Number(($event.target as HTMLInputElement).value)" type="number" class="form-input" min="0" max="50" />
                </div>
              </div>
              <!-- 该平台封面预览 -->
              <div v-if="store.platformCovers[p.id]" style="margin-bottom:14px">
                <div style="border-radius:8px;overflow:hidden;border:2px solid var(--primary);display:inline-block;background:var(--bg3)">
                  <img :src="coverUrl(store.platformCovers[p.id])" :alt="p.name + ' 封面'"
                       style="max-width:100%;max-height:200px;display:block"
                       @error="($event.target as HTMLImageElement).style.display='none'" />
                </div>
              </div>
            </div>
          </div>

          <!-- 单平台：原有布局 -->
          <div v-else>
            <div style="display:flex;gap:14px;margin-bottom:14px;flex-wrap:wrap">
              <div class="form-group" style="flex:1;min-width:160px">
                <label>拼接方式</label>
                <select v-model="coverLayout" class="form-select">
                  <option value="triple">三拼（3 张横向拼接）</option>
                  <option value="single">单图（单张裁剪）</option>
                  <option value="double">双拼</option>
                  <option value="wide">宽屏横版</option>
                  <option value="portrait">竖版</option>
                </select>
              </div>
              <div class="form-group" style="flex:1;min-width:160px">
                <label>封面尺寸</label>
                <select v-model="coverSize" class="form-select">
                  <option value="1300x640">1300 x 640（标准横版）</option>
                  <option value="800x450">800 x 450</option>
                  <option value="900x1200">900 x 1200（竖版）</option>
                </select>
              </div>
              <div class="form-group" style="flex:0.5;min-width:100px">
                <label>头顶留白 %</label>
                <input v-model.number="coverHeadroom" type="number" class="form-input" min="0" max="50" />
              </div>
            </div>
          </div>

          <button class="btn btn-primary" style="margin-bottom:14px" :disabled="isGeneratingCover" @click="handleGenerateCover">
            {{ isGeneratingCover ? '⏳ 生成中...' : '🖼️ 生成封面' }}
          </button>

          <!-- 单平台封面候选展示 -->
          <div v-if="!isMultiPlatform && store.coverCandidates.length" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">
            <div v-for="(c, i) in store.coverCandidates" :key="i"
                 style="border-radius:8px;overflow:hidden;cursor:pointer;position:relative;background:var(--bg3)"
                 :style="{border: store.selectedCover === i ? '2px solid var(--primary)' : '2px solid var(--bd)'}"
                 @click="store.selectedCover = i">
              <img :src="coverUrl(c)" :alt="'候选 ' + 'ABC'[i]"
                   style="width:100%;height:140px;object-fit:cover;display:block"
                   @error="($event.target as HTMLImageElement).style.display='none'" />
              <div style="padding:6px 8px;font-size:11px;color:var(--t2);text-align:center">
                封面
              </div>
              <div v-if="store.selectedCover === i" style="position:absolute;top:6px;right:6px;background:var(--primary);color:#000;font-size:10px;padding:2px 8px;border-radius:4px;font-weight:700">已选</div>
            </div>
          </div>
          <div style="margin-top:14px;display:flex;gap:8px">
            <button class="btn btn-green" :disabled="!store.coverCandidates.length && Object.keys(store.platformCovers).length === 0" @click="handleConfirmCover">✅ 使用封面，下一步 →</button>
            <button class="btn btn-ghost" :disabled="isGeneratingCover" @click="handleGenerateCover">🔄 重新生成</button>
            <button class="btn btn-ghost" @click="openImagePicker">📁 手动选图</button>
          </div>

          <!-- 手动选图弹窗 — 从已上传素材中选择 -->
          <div v-if="showImagePicker" class="modal-overlay" @click.self="showImagePicker = false">
            <div class="modal" style="max-width:700px">
              <div class="modal-head">
                <div class="modal-title">📁 从素材图片中选择</div>
                <button style="background:none;border:none;color:var(--t2);font-size:24px;cursor:pointer" @click="showImagePicker = false">&times;</button>
              </div>
              <div class="modal-body">
                <p style="font-size:12px;color:var(--t2);margin-bottom:12px">选择图片后将使用选中的图片生成封面（选 1 张 = 单图，选 2 张 = 双拼，选 3 张 = 三拼）</p>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px">
                  <div v-for="img in store.fileManifest.images" :key="img"
                       style="border-radius:6px;overflow:hidden;cursor:pointer;position:relative"
                       :style="{border: pickerSelectedImages.includes(img) ? '2px solid var(--primary)' : '2px solid var(--bd)'}"
                       @click="togglePickerImage(img)">
                    <img :src="coverUrl(store.folderPath + '/' + img)" style="width:100%;height:80px;object-fit:cover;display:block"
                         @error="($event.target as HTMLImageElement).style.display='none'" />
                    <div style="font-size:9px;padding:2px 4px;color:var(--t3);text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ img }}</div>
                    <div v-if="pickerSelectedImages.includes(img)"
                         style="position:absolute;top:2px;right:2px;background:var(--primary);color:#000;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">
                      {{ pickerSelectedImages.indexOf(img) + 1 }}
                    </div>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <span style="font-size:12px;color:var(--t2);margin-right:auto">已选 {{ pickerSelectedImages.length }} 张</span>
                <button class="btn btn-ghost" @click="showImagePicker = false">取消</button>
                <button class="btn btn-primary" :disabled="!pickerSelectedImages.length" @click="confirmPickerImages">生成封面</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 5: 水印（自动执行） -->
        <div v-if="store.currentStep === 4">
          <h4 style="margin-bottom:12px;font-size:14px">水印处理 <span style="font-size:12px;color:var(--t2);font-weight:400">— 自动执行中</span></h4>
          <!-- 处理进度 -->
          <div v-if="Object.values(store.wmProgress).some(p => ['running','done','failed','skipped'].includes(p.status))">
            <!-- 顶部消息：根据完成状态切换 -->
            <p v-if="wmAllDone" style="font-size:12px;color:var(--green);margin-bottom:14px">✅ 全部平台水印处理完成，即将自动进入发布步骤...</p>
            <p v-else style="font-size:12px;color:var(--t2);margin-bottom:14px">⏳ 正在为各平台添加水印，完成后将自动进入发布步骤…</p>
            <div style="display:flex;flex-direction:column;gap:10px">
              <div v-for="(info, pid) in store.wmProgress" :key="pid"
                   style="background:var(--bg3);border-radius:8px;padding:14px"
                   :style="{border: info.status==='done'?'1px solid var(--green)':info.status==='failed'?'1px solid var(--red)':info.status==='running'?'1px solid var(--primary)':'1px solid var(--bd)'}">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                  <span style="font-weight:600">{{ info.name || `平台 ${pid}` }}</span>
                  <span class="badge" style="font-size:10px"
                        :class="info.status==='done'?'badge-green':info.status==='skipped'?'badge-green':info.status==='failed'?'badge-red':info.status==='running'?'badge-primary':'badge-plain'">
                    {{ wmStatusLabel(info.status) }}
                  </span>
                </div>
                <div class="progress-bar" style="height:6px"><div class="progress-fill" :style="{width:info.progress+'%',background:info.status==='done'||info.status==='skipped'?'var(--green)':info.status==='failed'?'var(--red)':'var(--primary)'}" /></div>
                <div style="font-size:11px;margin-top:4px" :style="{color: info.status==='done'?'var(--green)':info.status==='failed'?'var(--red)':'var(--t3)'}">
                  <template v-if="info.status==='done'">
                    {{ wmDoneText(info) }}
                  </template>
                  <template v-else-if="info.status==='running'">正在添加水印…</template>
                  <template v-else-if="info.status==='failed'">{{ info.error || '处理失败' }}</template>
                  <template v-else-if="info.status==='skipped'">已跳过（未配置水印）</template>
                  <template v-else>排队中…</template>
                </div>
              </div>
            </div>
            <!-- 部分失败时允许手动继续 -->
            <div v-if="Object.values(store.wmProgress).some(p => p.status === 'failed') && !Object.values(store.wmProgress).some(p => p.status === 'running')"
                 style="margin-top:12px;padding:14px 16px;background:rgba(239,83,80,.06);border:1px solid rgba(239,83,80,.2);border-radius:8px;display:flex;align-items:center;justify-content:space-between">
              <span style="font-size:13px;color:var(--orange)">⚠️ 部分平台水印失败，可跳过继续发布</span>
              <button class="btn btn-primary" @click="handleWmDone">跳过失败，继续发布 →</button>
            </div>
          </div>
          <!-- 等待水印开始 -->
          <div v-else>
            <div style="padding:20px;background:var(--bg3);border-radius:8px;text-align:center">
              <div style="font-size:14px;color:var(--primary);margin-bottom:8px">⏳ 准备水印处理...</div>
              <div style="font-size:11px;color:var(--t3)">水印将根据各平台配置自动添加</div>
            </div>
          </div>
        </div>

        <!-- Step 6: 发布 -->
        <div v-if="store.currentStep === 5">
          <h4 style="margin-bottom:12px;font-size:14px">上传 & 发布 <span style="font-size:12px;color:var(--t2);font-weight:400">— 多平台并行上传，切片完成后逐一发布</span></h4>
          <div v-if="Object.keys(store.publishStatus).length === 0" style="color:var(--t3);padding:20px;text-align:center">
            <div style="font-size:24px;margin-bottom:8px">🚀</div>
            <div>正在自动发布中，请稍候...</div>
            <div style="font-size:11px;margin-top:4px">已选 {{ store.selectedPlatforms.length }} 个平台</div>
          </div>
          <div v-else style="display:flex;flex-direction:column;gap:10px">
            <div v-for="(info, pid) in store.publishStatus" :key="pid"
                 style="background:var(--bg3);border:1px solid var(--bd);border-radius:8px;padding:14px">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
                <div style="display:flex;align-items:center;gap:10px">
                  <span class="badge" :class="info.status==='published'?'badge-green':info.status==='failed'?'badge-red':info.status==='slice_pending'?'badge-orange':info.status==='publishing'?'badge-primary':'badge-plain'" style="font-size:10px;min-width:60px;justify-content:center">
                    {{ platformNameMap[pid] || `平台 ${pid}` }}
                  </span>
                  <span style="font-size:12px;font-weight:600" :style="{color: info.status==='published'?'var(--green)':info.status==='failed'?'var(--red)':info.status==='slice_pending'?'var(--orange)':info.status==='publishing'?'var(--primary)':'var(--t3)'}">
                    {{ info.status === 'published' ? '✅ 发布成功' : info.status === 'slice_pending' ? '⏳ 切片待确认' : info.status === 'failed' ? '❌ 发布失败' : info.status === 'publishing' ? '⏳ ' + (phaseLabel[info.phase || ''] || '准备中...') : '待发布' }}
                  </span>
                </div>
                <div style="display:flex;gap:6px">
                  <button v-if="info.status === 'failed'" class="btn btn-sm" style="color:var(--orange);border:1px solid var(--orange)"
                          @click="retryPlatform(Number(pid))">🔄 重试</button>
                  <button v-if="info.status === 'slice_pending'" class="btn btn-sm" style="color:var(--orange);border:1px solid var(--orange)"
                          @click="retryPlatform(Number(pid))">🔄 重新上传视频</button>
                  <button v-if="info.status === 'slice_pending'" class="btn btn-sm" style="color:var(--primary);border:1px solid var(--primary)"
                          @click="retryPlatform(Number(pid), true)">⏭️ 跳过视频，直接发布</button>
                </div>
              </div>
              <!-- 切片待确认提示 -->
              <div v-if="info.status === 'slice_pending'" style="margin-bottom:8px;padding:10px 14px;background:rgba(255,183,77,.08);border:1px solid rgba(255,183,77,.2);border-radius:6px;font-size:12px;color:var(--orange)">
                视频已上传，切片等待超时。请在 CMS 确认切片完成后，点击「一键发布」或到任务看板批量发布。
              </div>
              <div v-if="info.progress !== undefined && info.status === 'publishing'">
                <div class="progress-bar" style="height:6px;margin-bottom:4px">
                  <div class="progress-fill" :style="{width:info.progress+'%',background:'var(--primary)',transition:'width .5s ease'}" />
                </div>
                <div style="font-size:10px;color:var(--t3);display:flex;justify-content:space-between">
                  <span>{{ phaseLabel[info.phase || ''] || '' }}</span>
                  <span>{{ info.progress }}%</span>
                </div>
              </div>
              <div v-if="info.error" style="margin-top:4px">
                <details style="font-size:11px;color:var(--red);padding:6px 8px;background:rgba(239,83,80,.08);border-radius:4px;cursor:pointer">
                  <summary style="display:flex;align-items:center;gap:4px;user-select:none">⚠️ 错误信息（点击展开）</summary>
                  <pre style="margin-top:6px;white-space:pre-wrap;word-break:break-all;font-family:monospace;font-size:10px;line-height:1.5;max-height:200px;overflow-y:auto">{{ info.error }}</pre>
                </details>
              </div>
            </div>
          </div>
          <div style="margin-top:16px;display:flex;gap:10px;align-items:center">
            <button class="btn btn-green btn-lg" :disabled="!canPublish" @click="handlePublish">🚀 一键发布所有已就绪平台</button>
            <span style="font-size:12px;color:var(--t2)">
              {{ Object.values(store.publishStatus).filter((s: any) => s.status === 'published').length }} / {{ Object.keys(store.publishStatus).length }} 个平台已发布
            </span>
          </div>
          <!-- 发布进行中或完成后显示新建按钮 -->
          <div v-if="Object.keys(store.publishStatus).length > 0"
               style="margin-top:14px;padding:14px 16px;border-radius:8px;display:flex;align-items:center;justify-content:space-between"
               :style="Object.values(store.publishStatus).some((s: any) => s.status === 'publishing')
                 ? 'background:rgba(100,181,246,.06);border:1px solid rgba(100,181,246,.2)'
                 : 'background:rgba(129,199,132,.06);border:1px solid rgba(129,199,132,.2)'">
            <span style="font-size:13px" :style="{color: Object.values(store.publishStatus).some((s: any) => s.status === 'publishing') ? 'var(--primary)' : 'var(--green)'}">
              {{ Object.values(store.publishStatus).some((s: any) => s.status === 'publishing') ? '发布进行中，可先开始新任务' : '发布流程已完成' }}
            </span>
            <button class="btn btn-primary" @click="handleNewTask">＋ 新建发帖任务</button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div style="padding:16px 24px;border-top:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;gap:8px">
          <button v-if="store.currentStep > 0" class="btn btn-ghost btn-sm" @click="handlePrev">← 上一步</button>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span style="font-size:12px;color:var(--t3)">第 {{ store.currentStep + 1 }} 步 / 共 6 步</span>
          <span v-if="store.currentStep === 0 && !canNext()" style="font-size:11px;color:var(--t3)">选择素材和平台后自动进入下一步</span>
          <span v-if="store.currentStep === 0 && canNext()" style="font-size:11px;color:var(--primary)">即将自动进入文案生成...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-wrap { background: var(--bg2); border: 1px solid var(--bd); border-radius: 14px; overflow: hidden; }

.upload-zone {
  border: 2px dashed var(--bd); border-radius: 10px; padding: 32px 20px;
  text-align: center; color: var(--t3); cursor: pointer; transition: .2s;
}
.upload-zone:hover { border-color: var(--primary); color: var(--t2); background: rgba(79,195,247,.03); }
.upload-zone.dragging { border-color: var(--primary); background: rgba(79,195,247,.08); border-style: solid; }
.upload-zone.uploaded { border-color: var(--green); border-style: solid; background: rgba(129,199,132,.04); text-align: left; padding: 16px 20px; }
.upload-icon { font-size: 36px; margin-bottom: 8px; }
.upload-hint { font-size: 14px; font-weight: 500; }
.upload-sub { font-size: 11px; color: var(--t3); margin-top: 4px; }

/* AI generation loading animation */
.ai-loading-box {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 20px; gap: 12px;
}
.ai-loading-dots { display: flex; gap: 8px; }
.ai-loading-dots span {
  width: 10px; height: 10px; border-radius: 50%; background: var(--primary);
  animation: dot-pulse 1.4s ease-in-out infinite;
}
.ai-loading-dots span:nth-child(2) { animation-delay: .2s; }
.ai-loading-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes dot-pulse {
  0%, 80%, 100% { transform: scale(.4); opacity: .3; }
  40% { transform: scale(1); opacity: 1; }
}
.ai-loading-title { font-size: 14px; font-weight: 600; color: var(--primary); }
.ai-loading-sub { font-size: 12px; color: var(--t3); }
</style>
