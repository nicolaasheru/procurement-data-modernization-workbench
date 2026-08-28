"use client";

export default function ErrorPage({reset}:{error:Error&{digest?:string};reset:()=>void}){
  return <main className="recovery-page">
    <section>
      <span>The workbench could not finish this request</span>
      <h1>Your evidence is still safe.</h1>
      <p>The page could not finish rendering. Retry the current view, or refresh the browser if the interruption continues.</p>
      <button onClick={reset}>Try this view again →</button>
    </section>
  </main>;
}
