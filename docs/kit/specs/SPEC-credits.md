# Spec: credits

Module id: `credits`. Depends on `storage`.

## Objective

A user can see a balance. The balance moves only by inserting ledger rows. A standard generation costs 10. A new user receives 10 once.

## Commands

```
pnpm test lib/credits/ledger.test.ts
```

## Project structure

```
lib/credits/ledger.ts
lib/credits/ledger.test.ts
app/api/credits/route.ts     GET { balance: number }
```

## Behavior

```ts
export async function balanceOf(userId: string): Promise<number>
export async function grantTrial(userId: string, tx: Tx): Promise<void>
export async function debitGeneration(userId: string, generationId: string, tx: Tx): Promise<void>
```

`grantTrial` inserts `delta = 10`, `reason = trial`, only when that user has no `trial` row.

`debitGeneration` inserts `delta = -10`, `reason = debit_generation`, `generation_id` set. If `balanceOf` is under 10, it throws `InsufficientCredits` and writes nothing.

Both run inside the caller’s transaction. `debitGeneration` is called only from the generation success path, after the PNG is on disk. This module does not call the editor and does not call Stripe.

`GET /api/credits` returns the integer for the current user.

The top bar shows the integer in IBM Plex Mono. No credits: the generate button is disabled and its label is `No credits left.`

## Testing strategy

- New user plus `grantTrial` → balance 10. Second `grantTrial` → still 10.
- Debit → 0. Debit again throws and the sum stays 0.
- A rolled-back transaction leaves the sum unchanged.

## Boundaries

- Always: one transaction for the debit and the successful generation row.
- Ask first: changing the price away from 10, or adding a mutable balance column.
- Never: debit before the provider returns an image. Never decrement in the client.

## Success criteria

The three tests above pass. The UI number matches `GET /api/credits` after a reload.

## Open questions

None.
