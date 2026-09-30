import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

export const users = sqliteTable('users', {
  id: text('id').primaryKey(),
  email: text('email').notNull().unique(),
  name: text('name').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
});

export const images = sqliteTable('images', {
  id: text('id').primaryKey(),
  userId: text('user_id').notNull().references(() => users.id),
  width: integer('width').notNull(),
  height: integer('height').notNull(),
  storageKey: text('storage_key').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
});

export const ocrLines = sqliteTable('ocr_lines', {
  id: text('id').primaryKey(),
  imageId: text('image_id').notNull().references(() => images.id),
  text: text('text').notNull(),
  confidence: real('confidence').notNull(),
  x: integer('x').notNull(),
  y: integer('y').notNull(),
  width: integer('width').notNull(),
  height: integer('height').notNull(),
});

export const generations = sqliteTable('generations', {
  id: text('id').primaryKey(),
  userId: text('user_id').notNull().references(() => users.id),
  imageId: text('image_id').notNull().references(() => images.id),
  provider: text('provider').notNull(),
  model: text('model').notNull(),
  status: text('status').notNull(), // 'pending', 'succeeded', 'failed'
  outputKey: text('output_key'),
  error: text('error'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
});

export const generationReplacements = sqliteTable('generation_replacements', {
  // It probably needs an id, but the spec says:
  // "generation_replacements — generation_id, ocr_line_id nullable, from_text, to_text, x, y, width, height"
  // Let's create an id or primary key. No id specified, so composite PK? Or just auto id? I'll add an auto increment or let it be without PK if SQLite supports it, or use composite.
  // I will just add id as a convention if needed, wait, spec says exactly: "generation_id, ocr_line_id nullable..."
  // I'll leave it without an explicit primary key, SQLite allows tables without a declared primary key.
  generationId: text('generation_id').notNull().references(() => generations.id),
  ocrLineId: text('ocr_line_id').references(() => ocrLines.id),
  fromText: text('from_text').notNull(),
  toText: text('to_text').notNull(),
  x: integer('x').notNull(),
  y: integer('y').notNull(),
  width: integer('width').notNull(),
  height: integer('height').notNull(),
});

export const creditLedger = sqliteTable('credit_ledger', {
  id: text('id').primaryKey(),
  userId: text('user_id').notNull().references(() => users.id),
  delta: integer('delta').notNull(),
  reason: text('reason').notNull(),
  generationId: text('generation_id').references(() => generations.id),
  stripeEventId: text('stripe_event_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
});

export const stripeEvents = sqliteTable('stripe_events', {
  id: text('id').primaryKey(),
  receivedAt: integer('received_at', { mode: 'timestamp' }).notNull(),
});
