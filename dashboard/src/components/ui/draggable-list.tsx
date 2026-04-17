'use client'

import type { ReactNode } from 'react'
import { useState } from 'react'
import { GripVertical } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DraggableItem<T> {
  id: string
  data: T
}

interface DraggableListProps<T> {
  items: DraggableItem<T>[]
  onReorder: (items: DraggableItem<T>[]) => void
  renderItem: (item: DraggableItem<T>, index: number) => ReactNode
  className?: string
}

export function DraggableList<T>({
  items,
  onReorder,
  renderItem,
  className,
}: DraggableListProps<T>) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDragIndex(index)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(index))
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setOverIndex(index)
  }

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault()
    if (dragIndex === null || dragIndex === dropIndex) return
    const next = [...items]
    const [moved] = next.splice(dragIndex, 1)
    next.splice(dropIndex, 0, moved)
    onReorder(next)
    setDragIndex(null)
    setOverIndex(null)
  }

  const handleDragEnd = () => {
    setDragIndex(null)
    setOverIndex(null)
  }

  return (
    <div className={cn('space-y-2', className)}>
      {items.map((item, index) => (
        <div
          key={item.id}
          draggable
          onDragStart={(e) => handleDragStart(e, index)}
          onDragOver={(e) => handleDragOver(e, index)}
          onDrop={(e) => handleDrop(e, index)}
          onDragEnd={handleDragEnd}
          className={cn(
            'relative flex items-start gap-2 rounded-xl border bg-surface/55 transition-all',
            dragIndex === index
              ? 'opacity-40'
              : overIndex === index
                ? 'border-primary/50 bg-primary/10 scale-[1.01]'
                : 'border-border/70 hover:border-border'
          )}
        >
          <div
            className="ml-2 mt-3 cursor-grab text-muted-foreground/50 active:cursor-grabbing"
            title="Drag to reorder"
          >
            <GripVertical className="h-4 w-4" />
          </div>
          <div className="flex-1 py-2 pr-3">{renderItem(item, index)}</div>
        </div>
      ))}
    </div>
  )
}
