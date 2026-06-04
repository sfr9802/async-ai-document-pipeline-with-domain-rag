import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { RagPreviewPanel } from './RagPreviewPanel'

const forbiddenStrings = [
  'prompt',
  'raw_prompt',
  'raw_response',
  'raw response',
  'raw_llm_response',
  'expected_answer',
  'expected answer',
  'gold_label',
  'gold labels',
  'gold_qrels',
  'gold locator',
  'query_id',
  'case_id',
  'source_identity',
  'source_path',
  'source_title',
  'citation_locator',
  'supporting_evidence_id',
  'supporting_evidence_ids',
  'workbook',
  'file_name',
  'D:/private',
  'C:\\private',
  'hidden locator',
  'official_metric_input_rows_payload',
  'expected_answer_ko',
  'supporting_evidence_note',
  'include_in_official_denominator',
]

function mockFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function successBody() {
  return {
    answer: '매출 성장률은 75%입니다.',
    status: 'answered',
    route: '/api/rag/query',
    non_production_preview: true,
    production_routing: false,
    official_metric: false,
    promotion_evidence: false,
    product_success_evidence_allowed: false,
    live_db_index_cache_readiness: false,
    citations: [
      { source_family: 'XLSX', source_atom_id: 'xlsx-a1', sheet: 'Sheet1', table_or_range: 'A1', source_identity_hash: 'abc' },
      { source_family: 'PDF', source_atom_id: 'pdf-a1', page: 3, bbox: [10, 20, 30, 40], source_identity_hash: 'def' },
      { source_family: 'TEXT', source_atom_id: 'text-a1', title: '문서 발췌', section: '개요', source_identity_hash: 'ghi' },
    ],
    evidence_cards: [
      { source_family: 'XLSX', kind: 'xlsx', source_atom_id: 'xlsx-a1', display_value: '75%', sheet: 'Sheet1', matched_cells: ['A1'] },
      { source_family: 'PDF', kind: 'pdf', source_atom_id: 'pdf-a1', matched_text: 'PDF 근거', page: 3, bbox: [10, 20, 30, 40] },
      { source_family: 'TEXT', kind: 'text', source_atom_id: 'text-a1', matched_text: '텍스트 근거', section: ['개요'] },
    ],
    diagnostics: {
      redacted: true,
      llm_invoked: true,
      response_policy_bucket: 'ANSWERED',
      raw_prompt: 'raw response must never render',
      expected_answer: 'expected answer must never render',
      gold_label: 'gold label must never render',
      source_path: 'D:/private/report.pdf',
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('RagPreviewPanel', () => {
  test('submits preview query and renders answer, status, citations, and evidence cards without raw or gold fields', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch(successBody())
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), '매출 성장률 알려줘')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/rag/query',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('매출 성장률 알려줘'),
      }),
    )
    expect(await screen.findByText('매출 성장률은 75%입니다.')).toBeInTheDocument()
    expect(screen.getByText('answered')).toBeInTheDocument()
    expect(screen.getByText('XLSX')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
    expect(screen.getByText('TEXT')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('PDF 근거')).toBeInTheDocument()
    expect(screen.getByText('텍스트 근거')).toBeInTheDocument()
    for (const forbidden of forbiddenStrings) {
      expect(screen.queryByText(forbidden, { exact: false })).not.toBeInTheDocument()
    }
  })

  test('renders fail-closed backend response clearly without citations or evidence cards', async () => {
    const user = userEvent.setup()
    mockFetch({
      answer: '',
      status: 'backend_unavailable',
      citations: [],
      evidence_cards: [],
      diagnostics: {
        redacted: true,
        llm_invoked: false,
        fail_closed_reason: 'INDEX_UNAVAILABLE',
        response_policy_bucket: 'CONTRACT_VIOLATION',
      },
    })
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), 'A1 값')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(await screen.findByText('backend_unavailable')).toBeInTheDocument()
    expect(screen.getByText('INDEX_UNAVAILABLE')).toBeInTheDocument()
    expect(screen.getByText('답변 가능한 근거가 부족하거나 백엔드가 준비되지 않았습니다.')).toBeInTheDocument()
    expect(screen.queryByText('근거 카드')).not.toBeInTheDocument()
  })

  test('renders insufficient context and validation error preview statuses without forbidden details', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch({
      answer: '',
      status: 'insufficient_context',
      citations: [],
      evidence_cards: [],
      diagnostics: {
        redacted: true,
        llm_invoked: false,
        fail_closed_reason: 'raw_prompt D:/private/report.pdf expected_answer supporting_evidence_id query_id',
      },
    })
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), '이 표 값은?')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(await screen.findByText('insufficient_context')).toBeInTheDocument()
    for (const forbidden of forbiddenStrings) {
      expect(screen.queryByText(forbidden, { exact: false })).not.toBeInTheDocument()
    }

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          answer: '',
          status: 'validation_error',
          citations: [],
          evidence_cards: [],
          diagnostics: {
            redacted: true,
            llm_invoked: false,
            fail_closed_reason: 'citation_locator source_identity source_path source_title workbook file_name gold_qrels',
          },
        }),
      json: async () => ({
        answer: '',
        status: 'validation_error',
        citations: [],
        evidence_cards: [],
        diagnostics: {
          redacted: true,
          llm_invoked: false,
          fail_closed_reason: 'citation_locator source_identity source_path source_title workbook file_name gold_qrels',
        },
      }),
    })

    await user.clear(screen.getByLabelText('RAG preview query'))
    await user.type(screen.getByLabelText('RAG preview query'), '검증 오류 상태')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(await screen.findByText('validation_error')).toBeInTheDocument()
    for (const forbidden of forbiddenStrings) {
      expect(screen.queryByText(forbidden, { exact: false })).not.toBeInTheDocument()
    }
  })

  test('keeps invalid empty input local and does not call backend', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch(successBody())
    render(<RagPreviewPanel />)

    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('질문을 입력하세요.')).toBeInTheDocument()
  })

  test('sends bounded active context fields and omits hidden prompt or gold fields', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch(successBody())
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), 'A1 값')
    await user.click(screen.getByRole('button', { name: '활성 컨텍스트' }))
    await user.type(screen.getByLabelText('파일 ID'), 'Book.xlsx')
    await user.type(screen.getByLabelText('시트'), 'Sheet1')
    await user.type(screen.getByLabelText('위치'), 'A1')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    const call = fetchMock.mock.calls[0]
    const body = JSON.parse(String(call[1]?.body))
    expect(body.active_context).toEqual({
      file_id: 'Book.xlsx',
      sheet: 'Sheet1',
      locator_text: 'A1',
    })
    expect(JSON.stringify(body)).not.toContain('raw_prompt')
    expect(JSON.stringify(body)).not.toContain('expected_answer')
    expect(JSON.stringify(body)).not.toContain('gold')
  })

  test('renders citation rows as bounded frontend shapes', async () => {
    const user = userEvent.setup()
    mockFetch(successBody())
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), '근거 표시')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    const citations = await screen.findByLabelText('RAG preview citations')
    expect(within(citations).getByText('Sheet1')).toBeInTheDocument()
    expect(within(citations).getByText('page 3')).toBeInTheDocument()
    expect(within(citations).getByText('문서 발췌')).toBeInTheDocument()
  })

  test('uses composite citation and evidence keys so duplicate supporting evidence rows render without React key collisions', async () => {
    const user = userEvent.setup()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    mockFetch({
      ...successBody(),
      citations: [
        {
          source_family: 'TEXT',
          source_atom_id: 'text-dup',
          citation_key: 'citation:query-a-row-1-text-chunk-1',
          title: '중복 근거 A',
          section: '개요',
          supporting_evidence_id: 'shared-supporting-evidence',
          source_identity: 'TEXT:secret',
          source_path: 'D:/private/text-a.md',
          citation_locator: 'hidden locator',
        },
        {
          source_family: 'TEXT',
          source_atom_id: 'text-dup',
          citation_key: 'citation:query-a-row-2-text-chunk-2',
          title: '중복 근거 B',
          section: '개요',
          supporting_evidence_id: 'shared-supporting-evidence',
          source_identity: 'TEXT:secret',
          source_path: 'D:/private/text-b.md',
          citation_locator: 'hidden locator',
        },
      ],
      evidence_cards: [
        {
          source_family: 'TEXT',
          kind: 'text',
          source_atom_id: 'text-dup',
          matched_text: '중복 근거 A 본문',
          section: ['개요'],
          text_span: '1:8',
          supporting_evidence_id: 'shared-supporting-evidence',
        },
        {
          source_family: 'TEXT',
          kind: 'text',
          source_atom_id: 'text-dup',
          matched_text: '중복 근거 B 본문',
          section: ['개요'],
          text_span: '9:16',
          supporting_evidence_id: 'shared-supporting-evidence',
        },
      ],
    })
    render(<RagPreviewPanel />)

    await user.type(screen.getByLabelText('RAG preview query'), '중복 근거 표시')
    await user.click(screen.getByRole('button', { name: '미리보기 실행' }))

    expect(await screen.findByText('중복 근거 A')).toBeInTheDocument()
    expect(screen.getByText('중복 근거 B')).toBeInTheDocument()
    expect(screen.getByText('중복 근거 A 본문')).toBeInTheDocument()
    expect(screen.getByText('중복 근거 B 본문')).toBeInTheDocument()
    expect(consoleError).not.toHaveBeenCalledWith(expect.stringContaining('Encountered two children with the same key'), expect.anything())
    for (const forbidden of forbiddenStrings) {
      expect(screen.queryByText(forbidden, { exact: false })).not.toBeInTheDocument()
    }
    consoleError.mockRestore()
  })
})
