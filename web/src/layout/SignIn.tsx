import { ArrowRight } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { setToken } from "../app/session";
import { Field, Input } from "../design/Form";
import { Button } from "../design/primitives";

export function SignIn({ rejected }: { rejected: boolean }) {
  const [value, setValue] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (value.trim()) setToken(value.trim());
  }

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-panel p-4">
      <form onSubmit={submit} className="w-full max-w-sm animate-rise rounded-[20px] bg-surface p-8 shadow-float">
        <h1 className="text-[22px] text-ink">Sign in to ledgerkit</h1>
        <p className="mt-1.5 text-ink-2">
          This server requires an access token. Use the user token to work normally, or the agent token to see what an
          agent can do.
        </p>
        <Field
          label="Access token"
          className="mt-6"
          error={rejected ? "That token was not accepted. Check it and try again." : undefined}
          hint="Set as LEDGERKIT_USER_TOKEN or LEDGERKIT_AGENT_TOKEN on the server."
        >
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              autoFocus
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="primary" icon={ArrowRight} className="mt-6 w-full" disabled={!value.trim()}>
          Continue
        </Button>
      </form>
    </div>
  );
}
