import { Compass } from "@phosphor-icons/react";
import { Button, Card, EmptyState } from "../design/primitives";

export function NotFound() {
  return (
    <Card>
      <EmptyState
        icon={Compass}
        title="There is no page here"
        body="The address may be mistyped, or the page may have moved."
        action={
          <Button variant="tint" to="/">
            Back to the dashboard
          </Button>
        }
      />
    </Card>
  );
}
