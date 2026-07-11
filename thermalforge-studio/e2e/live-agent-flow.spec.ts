import { expect, test } from '@playwright/test'

const liveTaskId = process.env.THERMALFORGE_LIVE_TASK_ID

test('loads a completed task from the real API', async ({ page }) => {
  test.setTimeout(120_000)
  test.skip(!liveTaskId, 'Set THERMALFORGE_LIVE_TASK_ID to run live acceptance.')

  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') {
      runtimeErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.addInitScript((taskId) => {
    localStorage.setItem(
      'thermalforge.agent-session.v2',
      JSON.stringify({
        status: 'ready',
        backendStatus: 'ready',
        stage: 'ready',
        progress: 100,
        submitting: false,
        startRequested: true,
        cancelRequested: false,
        connection: 'disconnected',
        taskId,
        projectId: null,
        idempotencyKey: null,
        lastEventId: null,
        clarificationQuestion: null,
        clarificationAnswer: '',
        prompt: '真实 API 全流程验收',
        files: [],
        messages: [
          {
            id: 'message-1',
            role: 'agent',
            content: '真实任务已经完成，正在加载工程结果。',
            stage: 'ready',
            sequence: 1,
          },
        ],
        messageSequence: 1,
        inputError: null,
        isHistoryOpen: false,
        isExploded: false,
        selectedPart: null,
      }),
    )
  }, liveTaskId)

  await page.goto('/')

  await expect(page.getByText('设计已就绪').first()).toBeVisible()
  await expect(
    page.getByRole('button', { name: '切换到分件参考模型' }),
  ).toBeVisible({ timeout: 30_000 })
  await expect(
    page.getByRole('button', { name: '切换到整体参考模型' }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: '爆炸模型' })).toBeEnabled({
    timeout: 60_000,
  })

  await page.getByRole('button', { name: '开启自动旋转' }).click()
  await expect(
    page.getByRole('button', { name: '停止自动旋转' }),
  ).toBeVisible()
  await page.getByRole('button', { name: '开启线框模式' }).click()
  await expect(
    page.getByRole('button', { name: '关闭线框模式' }),
  ).toBeVisible()
  await page.getByRole('button', { name: '爆炸模型' }).click()
  await expect(page.getByRole('button', { name: '合并模型' })).toBeVisible()

  await page.getByRole('button', { name: '查看全部对话' }).click()
  const history = page.getByRole('dialog', { name: '完整对话' })
  await expect(history).toBeVisible()
  await history.getByRole('button', { name: '设计依据' }).click()
  await expect(history.locator('.evidence-heading h3')).not.toBeEmpty()
  await history.getByRole('button', { name: '后端输出' }).click()
  await expect(history.locator('pre')).toContainText('"project_title"')
  await expect(history.locator('pre')).not.toContainText(/api_key/i)

  expect(runtimeErrors).toEqual([])
})
