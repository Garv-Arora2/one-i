import { redirect } from "next/navigation";

// The newsroom front page lives at /home. Keep /events as a canonical alias.
export default function EventsPage() {
  redirect("/home");
}
