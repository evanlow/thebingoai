import { describe, it, expect } from 'vitest'
import { avatarColor, AVATAR_COLORS, initialFromLabel } from '~/utils/pipelineFormat'

describe('avatarColor', () => {
  it('is deterministic by id modulo the palette length', () => {
    expect(avatarColor(0)).toBe(AVATAR_COLORS[0])
    expect(avatarColor(1)).toBe(AVATAR_COLORS[1])
    expect(avatarColor(AVATAR_COLORS.length)).toBe(AVATAR_COLORS[0])  // wraps
    expect(avatarColor(AVATAR_COLORS.length + 2)).toBe(AVATAR_COLORS[2])
  })
})

describe('initialFromLabel', () => {
  it('strips the "type:" prefix and takes the first alnum char', () => {
    expect(initialFromLabel('Postgres : mydb')).toBe('M')
    expect(initialFromLabel('mysql : 123abc')).toBe('1')
  })

  it('skips leading non-alnum chars after the prefix', () => {
    expect(initialFromLabel('Type : ___foo')).toBe('F')
  })

  it('uses the whole label when there is no "type:" prefix', () => {
    expect(initialFromLabel('Connection #5')).toBe('C')
  })

  it('uppercases the initial', () => {
    expect(initialFromLabel('redis : abc')).toBe('A')
  })

  it('falls back to "#" when there is no alnum char', () => {
    expect(initialFromLabel('###')).toBe('#')
    expect(initialFromLabel('')).toBe('#')
  })
})
