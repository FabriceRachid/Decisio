# Frontend Notification Integration Guide

## Overview
This guide shows how to integrate the Django notification API into the React frontend to display step-by-step updates to users during upload and cleaning processes.

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/notifications/` | GET | List all notifications with filtering |
| `/api/auth/notifications/?is_read=false` | GET | Get only unread notifications |
| `/api/auth/notifications/1/` | GET | Get single notification details |
| `/api/auth/notifications/1/` | PATCH | Mark as read |
| `/api/auth/notifications/mark-all-read/` | POST | Mark all as read |

## React Hook for Notifications

### Custom Hook: `useNotifications`

```typescript
// hooks/useNotifications.ts
import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

export interface Notification {
  id: number
  type: 'ingestion_completed' | 'cleaning_started' | 'cleaning_progress' | 'cleaning_completed' | 'cleaning_failed'
  title: string
  message: string
  progress_percent: number
  is_read: boolean
  created_at: string
  action_url?: string
  data: {
    row_count?: number
    rows_affected?: number
    quality_score?: number
    error?: string
  }
}

export interface NotificationResponse {
  unread_count: number
  total_count: number
  notifications: Notification[]
}

export const useNotifications = () => {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch notifications from API
  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await axios.get<NotificationResponse>(
        '/api/auth/notifications/',
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      )
      setNotifications(response.data.notifications)
      setUnreadCount(response.data.unread_count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch notifications')
    } finally {
      setLoading(false)
    }
  }, [])

  // Mark notification as read
  const markAsRead = useCallback(async (notificationId: number) => {
    try {
      await axios.patch(
        `/api/auth/notifications/${notificationId}/`,
        {},
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      )
      // Update local state
      setNotifications(prev =>
        prev.map(n =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (err) {
      console.error('Failed to mark notification as read:', err)
    }
  }, [])

  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    try {
      await axios.post(
        '/api/auth/notifications/mark-all-read/',
        {},
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      )
      setNotifications(prev =>
        prev.map(n => ({ ...n, is_read: true }))
      )
      setUnreadCount(0)
    } catch (err) {
      console.error('Failed to mark all as read:', err)
    }
  }, [])

  // Auto-fetch on mount and set up polling
  useEffect(() => {
    fetchNotifications()
    
    // Poll for new notifications every 3 seconds
    const interval = setInterval(fetchNotifications, 3000)
    
    return () => clearInterval(interval)
  }, [fetchNotifications])

  return {
    notifications,
    unreadCount,
    loading,
    error,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
  }
}
```

## Toast Notification Component

### Simple Toast Display

```typescript
// components/NotificationToast.tsx
import React from 'react'
import { Notification } from '../hooks/useNotifications'

interface NotificationToastProps {
  notification: Notification
  onClose?: () => void
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  notification,
  onClose
}) => {
  React.useEffect(() => {
    if (notification.type === 'ingestion_completed' || 
        notification.type === 'cleaning_completed') {
      // Keep success/completion notifications longer (5s)
      const timer = setTimeout(onClose, 5000)
      return () => clearTimeout(timer)
    } else if (notification.type === 'cleaning_failed') {
      // Keep error notifications longer (7s)
      const timer = setTimeout(onClose, 7000)
      return () => clearTimeout(timer)
    } else {
      // Keep progress notifications shorter (2s)
      const timer = setTimeout(onClose, 2000)
      return () => clearTimeout(timer)
    }
  }, [notification, onClose])

  const getBackgroundColor = () => {
    switch (notification.type) {
      case 'ingestion_completed':
      case 'cleaning_completed':
        return 'bg-green-100 border-green-500'
      case 'cleaning_failed':
        return 'bg-red-100 border-red-500'
      case 'cleaning_started':
      case 'cleaning_progress':
        return 'bg-blue-100 border-blue-500'
      default:
        return 'bg-gray-100 border-gray-500'
    }
  }

  const getTextColor = () => {
    switch (notification.type) {
      case 'ingestion_completed':
      case 'cleaning_completed':
        return 'text-green-800'
      case 'cleaning_failed':
        return 'text-red-800'
      case 'cleaning_started':
      case 'cleaning_progress':
        return 'text-blue-800'
      default:
        return 'text-gray-800'
    }
  }

  return (
    <div className={`border-l-4 p-4 ${getBackgroundColor()} rounded shadow-lg mb-2`}>
      <div className={`font-bold ${getTextColor()}`}>
        {notification.title}
      </div>
      <div className={`text-sm ${getTextColor()}`}>
        {notification.message}
      </div>
      {notification.progress_percent > 0 && notification.progress_percent < 100 && (
        <div className="mt-2 bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${notification.progress_percent}%` }}
          />
        </div>
      )}
    </div>
  )
}
```

## Notification Container Component

### Display Multiple Notifications

```typescript
// components/NotificationContainer.tsx
import React, { useState } from 'react'
import { Notification, useNotifications } from '../hooks/useNotifications'
import { NotificationToast } from './NotificationToast'

export const NotificationContainer: React.FC = () => {
  const { notifications, unreadCount, markAsRead } = useNotifications()
  const [displayedNotifications, setDisplayedNotifications] = useState<Notification[]>([])

  // Show only unread notifications as toasts
  React.useEffect(() => {
    const unreadNotifications = notifications.filter(n => !n.is_read)
    setDisplayedNotifications(unreadNotifications)
  }, [notifications])

  const handleRemoveNotification = (notificationId: number) => {
    setDisplayedNotifications(prev =>
      prev.filter(n => n.id !== notificationId)
    )
    markAsRead(notificationId)
  }

  return (
    <div className="fixed top-4 right-4 z-50 w-96 max-w-full">
      {displayedNotifications.map(notification => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onClose={() => handleRemoveNotification(notification.id)}
        />
      ))}

      {/* Badge showing unread count */}
      {unreadCount > 0 && (
        <div className="fixed bottom-4 right-4">
          <button className="relative">
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M15 17H4V5h14v7h2V5c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h11v-2z"/>
            </svg>
            <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-600 rounded-full">
              {unreadCount}
            </span>
          </button>
        </div>
      )}
    </div>
  )
}
```

## Notification Panel Component

### Detailed Notification History

```typescript
// components/NotificationPanel.tsx
import React from 'react'
import { Notification, useNotifications } from '../hooks/useNotifications'

export const NotificationPanel: React.FC = () => {
  const { 
    notifications, 
    unreadCount, 
    markAsRead, 
    markAllAsRead 
  } = useNotifications()

  const getIcon = (type: string) => {
    switch (type) {
      case 'ingestion_completed':
        return '✅'
      case 'cleaning_started':
      case 'cleaning_progress':
        return '🔄'
      case 'cleaning_completed':
        return '✅'
      case 'cleaning_failed':
        return '❌'
      default:
        return 'ℹ️'
    }
  }

  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="bg-white rounded-lg shadow-lg max-w-md">
      {/* Header */}
      <div className="p-4 border-b flex justify-between items-center">
        <h2 className="text-lg font-bold">
          Notifications {unreadCount > 0 && `(${unreadCount})`}
        </h2>
        {unreadCount > 0 && (
          <button
            onClick={markAllAsRead}
            className="text-sm text-blue-600 hover:underline"
          >
            Mark all as read
          </button>
        )}
      </div>

      {/* Notifications List */}
      <div className="divide-y max-h-96 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            No notifications yet
          </div>
        ) : (
          notifications.map(notification => (
            <div
              key={notification.id}
              className={`p-4 cursor-pointer hover:bg-gray-50 transition ${
                !notification.is_read ? 'bg-blue-50' : ''
              }`}
              onClick={() => !notification.is_read && markAsRead(notification.id)}
            >
              <div className="flex items-start">
                <span className="text-2xl mr-3">{getIcon(notification.type)}</span>
                <div className="flex-1">
                  <div className="font-bold text-sm">{notification.title}</div>
                  <div className="text-xs text-gray-600">{notification.message}</div>
                  
                  {/* Progress bar if in progress */}
                  {notification.progress_percent > 0 && 
                   notification.progress_percent < 100 && (
                    <div className="mt-2 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${notification.progress_percent}%` }}
                      />
                    </div>
                  )}

                  {/* Additional data if available */}
                  {notification.data && Object.keys(notification.data).length > 0 && (
                    <div className="mt-2 text-xs text-gray-500">
                      {notification.data.row_count && `Rows: ${notification.data.row_count}`}
                      {notification.data.rows_affected && `Affected: ${notification.data.rows_affected}`}
                      {notification.data.quality_score && `Quality: ${notification.data.quality_score.toFixed(1)}%`}
                      {notification.data.error && `Error: ${notification.data.error}`}
                    </div>
                  )}

                  <div className="text-xs text-gray-400 mt-1">
                    {getTimeAgo(notification.created_at)}
                  </div>
                </div>
                {!notification.is_read && (
                  <div className="w-2 h-2 bg-blue-600 rounded-full mt-1 ml-2" />
                )}
              </div>

              {/* Action button if available */}
              {notification.action_url && (
                <div className="mt-2">
                  <a
                    href={notification.action_url}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    View Details →
                  </a>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
```

## Integration in Main App

### App.tsx Setup

```typescript
// App.tsx
import { NotificationContainer } from './components/NotificationContainer'
import { NotificationPanel } from './components/NotificationPanel'

function App() {
  return (
    <div className="App">
      {/* Always show floating toast notifications */}
      <NotificationContainer />

      {/* Optional: Show notification panel in sidebar/drawer */}
      <div className="flex">
        <main className="flex-1">
          {/* Your main content */}
        </main>
        <aside className="w-80 border-l p-4 bg-gray-50">
          <NotificationPanel />
        </aside>
      </div>
    </div>
  )
}

export default App
```

## Handling Specific Notification Types

### Upload → Clean → Complete Sequence

```typescript
// hooks/useUploadWithNotifications.ts
import { useState, useCallback } from 'react'
import { useNotifications } from './useNotifications'
import axios from 'axios'

export const useUploadWithNotifications = () => {
  const { notifications, fetchNotifications } = useNotifications()
  const [isUploading, setIsUploading] = useState(false)

  const uploadFile = useCallback(async (file: File) => {
    setIsUploading(true)
    
    try {
      // Upload file
      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(
        '/api/ingestion/upload/',
        formData,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            'Content-Type': 'multipart/form-data'
          }
        }
      )

      const sourceId = response.data.id

      // Watch for notifications
      let cleaningComplete = false
      let lastProgress = 0

      const checkForCompletion = setInterval(() => {
        const sourceNotifications = notifications.filter(n => n.source_id === sourceId)
        
        // Check if cleaning completed
        const completedNotif = sourceNotifications.find(
          n => n.type === 'cleaning_completed'
        )
        if (completedNotif) {
          cleaningComplete = true
          clearInterval(checkForCompletion)
          console.log('Cleaning complete!', completedNotif.data)
        }

        // Log progress
        const progressNotif = sourceNotifications.find(
          n => n.type === 'cleaning_progress' && n.progress_percent > lastProgress
        )
        if (progressNotif) {
          lastProgress = progressNotif.progress_percent
          console.log(`Progress: ${progressNotif.progress_percent}%`)
        }
      }, 500)

      // Set timeout to stop checking after 5 minutes
      setTimeout(() => clearInterval(checkForCompletion), 300000)

      return sourceId
    } catch (err) {
      console.error('Upload failed:', err)
      throw err
    } finally {
      setIsUploading(false)
    }
  }, [notifications])

  return {
    uploadFile,
    isUploading,
  }
}
```

## WebSocket Alternative (Optional)

For real-time updates without polling:

```typescript
// hooks/useNotificationsWebSocket.ts
import { useEffect, useState, useCallback } from 'react'

export const useNotificationsWebSocket = () => {
  const [notifications, setNotifications] = useState([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
      // Send auth token
      ws.send(JSON.stringify({
        type: 'auth',
        token: localStorage.getItem('access_token')
      }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'notification') {
        setNotifications(prev => [data.notification, ...prev])
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setIsConnected(false)
    }

    ws.onclose = () => {
      setIsConnected(false)
    }

    return () => ws.close()
  }, [])

  return { notifications, isConnected }
}
```

## Summary

1. **Use `useNotifications` hook** to fetch and manage notifications
2. **Display toasts** with `NotificationToast` for active events
3. **Show panel** with `NotificationPanel` for history
4. **Handle sequences** like Upload → Clean → Complete
5. **Optional WebSocket** for true real-time if polling is sluggish
6. **Auto-cleanup** old notifications from localStorage/state

This provides users with transparent, step-by-step feedback during their workflows.