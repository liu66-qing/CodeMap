import { useEffect, useRef, useState } from 'react'
import {
  api,
  AnalysisFullResponse,
  AnalysisStatusResponse,
} from '../services/api'

/**
 * Submit a repo for multi-agent analysis and poll until complete.
 *
 * Usage:
 *   const { taskId, status, result, error, start } = useAnalyzeRepo()
 *   start('https://github.com/dbader/schedule')
 *
 * The hook:
 *  - calls POST /analysis/repos/analyze on `start`
 *  - polls GET /analysis/repos/{task_id}/status every `pollMs` (default 2s)
 *  - once status === 'done', fetches the full result and exposes it
 *  - stops polling on done/failed or when the component unmounts
 */
export interface UseAnalyzeRepoState {
  taskId: string | null
  status: AnalysisStatusResponse['status'] | 'idle'
  progress: AnalysisStatusResponse['progress']
  result: AnalysisFullResponse['result'] | null
  error: string | null
  isRunning: boolean
}

export function useAnalyzeRepo(pollMs: number = 2000) {
  const [state, setState] = useState<UseAnalyzeRepoState>({
    taskId: null,
    status: 'idle',
    progress: {},
    result: null,
    error: null,
    isRunning: false,
  })
  const timerRef = useRef<number | null>(null)
  const cancelRef = useRef(false)

  const stopPolling = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  useEffect(() => {
    return () => {
      cancelRef.current = true
      stopPolling()
    }
  }, [])

  const start = async (repoUrl: string) => {
    cancelRef.current = false
    stopPolling()
    setState((s) => ({
      ...s,
      taskId: null,
      status: 'running',
      progress: {},
      result: null,
      error: null,
      isRunning: true,
    }))

    try {
      const { task_id } = await api.startAnalysis(repoUrl)
      if (cancelRef.current) return
      setState((s) => ({ ...s, taskId: task_id }))
      poll(task_id)
    } catch (err) {
      setState((s) => ({
        ...s,
        status: 'failed',
        error: err instanceof Error ? err.message : String(err),
        isRunning: false,
      }))
    }
  }

  const poll = (taskId: string) => {
    const tick = async () => {
      if (cancelRef.current) return
      try {
        const status = await api.getAnalysisStatus(taskId)
        if (cancelRef.current) return
        setState((s) => ({ ...s, status: status.status, progress: status.progress }))
        if (status.status === 'done') {
          const full = await api.getAnalysisFull(taskId)
          if (cancelRef.current) return
          setState((s) => ({
            ...s,
            result: full.result,
            isRunning: false,
          }))
          return
        }
        if (status.status === 'failed') {
          setState((s) => ({
            ...s,
            error: status.error || 'analysis failed',
            isRunning: false,
          }))
          return
        }
        timerRef.current = window.setTimeout(tick, pollMs)
      } catch (err) {
        setState((s) => ({
          ...s,
          status: 'failed',
          error: err instanceof Error ? err.message : String(err),
          isRunning: false,
        }))
      }
    }
    tick()
  }

  return { ...state, start }
}
