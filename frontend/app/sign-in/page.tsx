import { SignIn } from "@/components/SignIn";
import { api } from "@/lib/api";

export const metadata = {
  title: "Sign in",
};

export const dynamic = "force-dynamic";

export default async function SignInPage() {
  const config = await api.authConfig();

  return (
    <div
      style={{
        maxWidth: "44rem",
        margin: "0 auto",
        padding: "clamp(2.5rem, 6vw, 4rem) var(--gutter) 0",
      }}
    >
      <p className="kicker kicker-accent">Your account</p>
      <h1>Sign in</h1>
      <p className="standfirst" style={{ maxWidth: "52ch" }}>
        ONE I uses Google to sign you in, so no password is ever created or
        stored here. Signing in is only used to remember you between visits.
      </p>

      <SignIn config={config} />

      <p className="note" style={{ marginTop: "1.5rem" }}>
        Reading ONE I does not require an account. Every event, timeline and
        comparison is open to anyone.
      </p>
    </div>
  );
}
