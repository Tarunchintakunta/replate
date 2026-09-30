import { migrate } from 'drizzle-orm/better-sqlite3/migrator';
import { db, sqlite } from './client';

console.log('Running migrations...');
migrate(db, { migrationsFolder: 'db/migrations' });
console.log('Migrations complete!');
sqlite.close();
