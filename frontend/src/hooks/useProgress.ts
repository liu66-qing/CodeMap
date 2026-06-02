import { useCallback, useEffect, useRef, useState } from 'react'
import { api, LearningMapStats } from '../services/api'

const DEFAULT_USER = 'default'

/**
 * Hook for recording learning events and fetching map stats.
 *
 * Usage in stage pages:
 *   const { visit, recordTimeSpent } = useProgress()
 *   useEffect(() => { visit('overview', taskId, repoUrl) }, [])
 *
 * Usage in LearningMap page:
 *   const { stats, refresh } = useProgress()
 */
export function useProgress(userId: string = DEFAULT_USER) {
  const [stats, setStats] = useState<LearningMapStats | null>(null)
  const [loading, setLoading] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getLearningStats(userId)
      if (mountedRef.current) setStats(data)
    } catch {
      // silent
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [userId])

  // Auto-fetch on mount
  useEffect(() => { refresh() }, [refresh])

  const visit = useCallback(
    async (stage: string, taskId?: string, repoUrl?: string) => {
      await api.recordLearningEvent({
        user_id: userId,
        task_id: taskId,
        repo_url: repoUrl,
        stage,
        type: 'visit',
      })
    },
    [userId]
  )

  const recordTimeSpent = useCallback(
    async (stage: string, seconds: number, taskId?: string, repoUrl?: string) => {
      await api.recordLearningEvent({
        user_id: userId,
        task_id: taskId,
        repo_url: repoUrl,
        stage,
        type: 'time_spent',
        value: seconds,
      })
    },
    [userId]
  )

  const recordHighlightRead = useCallback(
    async (stage: string, taskId?: string, repoUrl?: string) => {
      await api.recordLearningEvent({
        user_id: userId,
        task_id: taskId,
        repo_url: repoUrl,
        stage,
        type: 'highlight_read',
      })
    },
    [userId]
  )

  const recordPatternCopied = useCallback(
    async (stage: string, taskId?: string, repoUrl?: string) => {
      await api.recordLearningEvent({
        user_id: userId,
        task_id: taskId,
        repo_url: repoUrl,
        stage,
        type: 'pattern_copied',
      })
    },
    [userId]
  )

  return {
    stats,
    loading,
    refresh,
    visit,
    recordTimeSpent,
    recordHighlightRead,
    recordPatternCopied,
  }
}
