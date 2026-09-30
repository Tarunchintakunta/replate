import { db } from '../../db/client';
import { users, creditLedger } from '../../db/schema';
import { eq } from 'drizzle-orm';
import { v4 as uuidv4 } from 'uuid';

export async function currentUser() {
  const email = 'local@replate.test';
  
  const [existingUser] = await db.select().from(users).where(eq(users.email, email));
  if (existingUser) {
    return existingUser;
  }

  // Not using a transaction here because better-sqlite3 transactions cannot easily mix with async/await
  // under the Drizzle generic wrapper without `.all()` synchronous calls.
  // This is safe since it's just the bootstrap user on local development.

  const newUserId = uuidv4();
  const newUser = {
    id: newUserId,
    email,
    name: 'Local Dev',
    createdAt: new Date(),
  };
  await db.insert(users).values(newUser);

  const ledgerId = uuidv4();
  await db.insert(creditLedger).values({
    id: ledgerId,
    userId: newUserId,
    delta: 10,
    reason: 'trial',
    createdAt: new Date(),
  });

  return newUser;
}
