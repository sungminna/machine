import ChatInterface from "./ChatInterface";

export default function Home() {
  return (
    <div className="flex">
      <main className="w-screen h-screen">
        <ChatInterface />
      </main>
    </div>
  );
}