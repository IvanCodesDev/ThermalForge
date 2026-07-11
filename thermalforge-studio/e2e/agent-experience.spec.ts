import { expect, test } from '@playwright/test'

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'low-height-landscape', width: 844, height: 390 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
] as const

function collectRuntimeErrors(page: Parameters<typeof test>[0]['page']) {
  const errors: string[] = []

  page.on('console', (message) => {
    if (message.type() === 'error') {
      errors.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    errors.push(error.message)
  })

  return errors
}

async function installReadyTaskApi(
  page: Parameters<typeof test>[0]['page'],
) {
  const createdAt = '2026-07-11T00:00:00Z'
  const project = {
    id: 'project-e2e',
    name: '机器人关节热增强',
    created_at: createdAt,
  }
  const task = {
    id: 'task-e2e',
    project_id: project.id,
    status: 'created',
    stage: 'created',
    prompt: '降低膝关节热点温度，并保持热增强外壳可拆卸。',
    idempotency_key: 'e2e-request',
    created_at: createdAt,
    updated_at: createdAt,
  }
  const modelDataUrl = `data:model/stl;base64,${Buffer.from(
    [
      'solid e2e',
      'facet normal 0 0 1',
      'outer loop',
      'vertex 0 0 0',
      'vertex 1 0 0',
      'vertex 0 1 0',
      'endloop',
      'endfacet',
      'endsolid e2e',
    ].join('\n'),
  ).toString('base64')}`
  const imageDataUrl =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='

  await page.route('**/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const fulfillJson = (status: number, body: unknown) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })

    if (method === 'POST' && path === '/v1/projects') {
      return fulfillJson(201, project)
    }
    if (method === 'POST' && path === `/v1/projects/${project.id}/tasks`) {
      return fulfillJson(201, task)
    }
    if (method === 'POST' && path === `/v1/tasks/${task.id}/documents`) {
      return fulfillJson(201, {
        id: 'artifact-e2e',
        task_id: task.id,
        kind: 'source_document',
        version: 1,
        mime_type: 'text/plain',
        sha256: '1234567890abcdef',
        size_bytes: 16,
        storage_uri: 'local://requirements.txt',
        metadata: {},
        quality_status: 'approved',
        created_at: createdAt,
      })
    }
    if (method === 'POST' && path === `/v1/tasks/${task.id}/start`) {
      return fulfillJson(200, {
        ...task,
        status: 'ready',
        stage: 'ready',
      })
    }
    if (method === 'GET' && path === '/v1/viewer-library') {
      return fulfillJson(200, { schema_version: '1.0', models: [] })
    }
    if (
      method === 'GET' &&
      path === `/v1/tasks/${task.id}/engineering-brief`
    ) {
      return fulfillJson(200, {
        project_title: '机器人关节热增强',
        heat_sources: [{ name: '电机', power_w: 120 }],
        overall_confidence: 1,
      })
    }
    if (
      method === 'GET' &&
      path === `/v1/tasks/${task.id}/thermal-analysis`
    ) {
      return fulfillJson(200, {
        source: 'engineering-estimate',
        baseline: {
          maxTemperatureC: 96,
          timeToLimitMinutes: 18,
        },
        riskLevel: 'High',
        warnings: ['筛选结果尚未经过样机校准'],
      })
    }
    if (
      method === 'GET' &&
      path === `/v1/tasks/${task.id}/thermal-design`
    ) {
      return fulfillJson(200, {
        baseline_max_temperature_c: 96,
        selected_solution: {
          title: '叶脉扩散外壳',
          max_temperature_c: 72,
          hotspot_reduction_c: 24,
        },
        rationale: '降低热点并保持原厂安装孔位。',
        heat_transfer_path: ['电机', '导热环', '扩散外壳', '环境空气'],
        material_recommendations: ['6061-T6 铝合金'],
        assumptions: [],
        risks: [],
        unverified_items: ['动态干涉'],
        requires_human_confirmation: true,
      })
    }
    if (
      method === 'GET' &&
      path === `/v1/tasks/${task.id}/image-manifest`
    ) {
      return fulfillJson(200, {
        schema_version: '1.0',
        task_id: task.id,
        images: [
          'mother_three_quarter',
          'front',
          'left',
          'rear',
          'top',
          'elbow_section',
        ].map((viewId, index) => ({
          artifact_id: `image-${index}`,
          kind: index === 0 ? 'concept_image' : 'multiview_image',
          view_id: viewId,
          url: imageDataUrl,
          mime_type: 'image/png',
          sha256: `${index}`.repeat(64),
          size_bytes: 68,
          provider: 'openai_compatible',
          provider_model: 'gpt-image-2',
        })),
        notice: '概念图用于方案沟通，不是制造验证结果。',
      })
    }
    if (method === 'GET' && path === `/v1/tasks/${task.id}/viewer-manifest`) {
      return fulfillJson(200, {
        schema_version: '1.0',
        task_id: task.id,
        asset: {
          artifact_id: 'model-e2e',
          kind: 'normalized_model',
          url: modelDataUrl,
          format: 'stl',
          mime_type: 'model/stl',
          sha256: '1234567890abcdef',
          size_bytes: 115,
          transform: {
            translation: [0, 0, 0],
            rotation: [0, 0, 0, 1],
            scale: [1, 1, 1],
          },
        },
      })
    }

    return fulfillJson(404, {
      code: 'e2e_route_not_found',
      message: `${method} ${path} is not mocked.`,
    })
  })
}

for (const viewport of VIEWPORTS) {
  test(`keeps the 3D model central at ${viewport.name} size`, async ({
    page,
  }, testInfo) => {
    const runtimeErrors = collectRuntimeErrors(page)
    await page.route('**/v1/viewer-library', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ schema_version: '1.0', models: [] }),
      }),
    )
    await page.setViewportSize(viewport)
    await page.goto('/')

    await expect(
      page.getByRole('region', { name: '三维关节模型' }),
    ).toBeVisible()
    await expect(page.locator('canvas')).toBeVisible()
    const designInput = page.getByRole('textbox', { name: '设计目标' })
    await expect(designInput).toBeVisible()

    const viewportMetrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(viewportMetrics.scrollWidth).toBeLessThanOrEqual(
      viewportMetrics.clientWidth + 1,
    )

    const modelBounds = await page
      .getByRole('region', { name: '三维关节模型' })
      .boundingBox()
    expect(modelBounds).not.toBeNull()
    expect(modelBounds!.width).toBeGreaterThan(viewport.width * 0.9)
    expect(modelBounds!.height).toBeGreaterThan(viewport.height * 0.7)

    const inputBounds = await designInput.boundingBox()
    expect(inputBounds).not.toBeNull()
    expect(inputBounds!.y).toBeGreaterThanOrEqual(0)
    expect(inputBounds!.y + inputBounds!.height).toBeLessThanOrEqual(
      viewport.height + 1,
    )

    if (viewport.name !== 'low-height-landscape') {
      await page.screenshot({
        path: testInfo.outputPath(`thermalforge-${viewport.name}.png`),
        fullPage: true,
      })
    }
    expect(runtimeErrors).toEqual([])
  })
}

test('runs the API-backed flow and exposes model controls', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await installReadyTaskApi(page)
  await page.goto('/')

  await page.getByLabel('上传工程文档').setInputFiles({
    name: 'requirements.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Maximum shell temperature: 70 C'),
  })
  await page
    .getByRole('textbox', { name: '设计目标' })
    .fill('降低膝关节热点温度，并保持热增强外壳可拆卸。')
  await page.getByRole('button', { name: '开始生成' }).click()

  await expect(page.getByText('设计已就绪').first()).toBeVisible({
    timeout: 10_000,
  })
  await expect(page.getByText('任务工程模型 · STL')).toBeVisible()

  const explodeButton = page.getByRole('button', { name: '爆炸模型' })
  await expect(explodeButton).toBeDisabled()
  await expect(
    page.getByRole('button', { name: '重置模型视角' }),
  ).toBeEnabled()
  const inspectButton = page.getByRole('button', { name: '查看资产信息' })
  await expect(inspectButton).toBeEnabled()
  await inspectButton.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('部件设计说明')).toBeVisible()
  await page.getByRole('button', { name: '关闭部件说明' }).click()

  await page.getByRole('button', { name: '查看全部对话' }).click()
  await expect(page.getByRole('dialog', { name: '完整对话' })).toBeVisible()
  await page.getByRole('button', { name: '概念图' }).click()
  await expect(page.getByRole('img', { name: '母图三季度视角' })).toBeVisible()
  await expect(page.locator('.concept-image-grid img')).toHaveCount(6)
  expect(runtimeErrors).toEqual([])
})

test('respects reduced-motion preferences', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await page
    .getByRole('textbox', { name: '设计目标' })
    .fill('生成低矮散热鳍片')
  await page.getByRole('button', { name: '开始生成' }).click()

  const animationDuration = await page
    .locator('.session-status')
    .evaluate((element) => getComputedStyle(element).animationDuration)

  expect(Number.parseFloat(animationDuration)).toBeLessThan(0.001)
})

test('keeps core controls keyboard reachable', async ({ page }) => {
  await page.goto('/')

  const uploadInput = page.getByLabel('上传工程文档')
  const prompt = page.getByRole('textbox', { name: '设计目标' })
  const submit = page.getByRole('button', { name: '开始生成' })

  await uploadInput.focus()
  await expect(uploadInput).toBeFocused()
  await prompt.focus()
  await page.keyboard.press('Tab')
  await expect(submit).toBeFocused()
})

test('accepts an engineering case dropped onto the composer', async ({
  page,
}) => {
  await page.route('**/v1/viewer-library', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ schema_version: '1.0', models: [] }),
    }),
  )
  await page.goto('/')

  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer()
    transfer.items.add(
      new File(
        ['持续热耗散 120 W，最高环境温度 35 °C。'],
        'foc-joint-case.md',
        { type: 'text/markdown' },
      ),
    )
    return transfer
  })
  const composer = page.getByRole('form', { name: '设计请求输入' })
  await composer.dispatchEvent('dragenter', { dataTransfer })
  await expect(page.getByText('松开即可上传工程资料')).toBeVisible()
  await composer.dispatchEvent('drop', { dataTransfer })

  await expect(page.getByText('foc-joint-case.md')).toBeVisible()
})

test('keeps the WebGL scene responsive under CPU throttling', async ({
  page,
  context,
}) => {
  const cdp = await context.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  await page.goto('/')
  await expect(page.locator('canvas')).toBeVisible()

  const frameDurationMs = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const startedAt = performance.now()
        let frameCount = 0

        const measureFrame = () => {
          frameCount += 1
          if (frameCount === 20) {
            resolve(performance.now() - startedAt)
            return
          }
          requestAnimationFrame(measureFrame)
        }

        requestAnimationFrame(measureFrame)
      }),
  )

  expect(frameDurationMs).toBeLessThan(5_000)
})
