import LightRays from './components/LightRays'
import SideRays from './components/SideRays'
import FloatingLines from './components/FloatingLines'
import SplitText from './components/SplitText'

export default function App() {
  return (
    <main className="bg-[#0a0a0f] text-white">
      {/* 第一屏：LightRays（≈ Pro 的 falling-rays）+ SplitText 标题 */}
      <section className="relative flex h-screen items-center justify-center overflow-hidden">
        <LightRays
          className="absolute inset-0 -z-10"
          raysOrigin="top-center"
          raysColor="#facc15"
          rayLength={1.2}
          raysSpeed={1.5}
        />
        <SplitText
          text="React Bits 组件演示"
          className="text-6xl font-bold"
          delay={50}
        />
      </section>

      {/* 第二屏：FloatingLines（≈ Pro 的 rising-lines / long-exposure） */}
      <section className="relative flex h-screen items-center justify-center overflow-hidden">
        <FloatingLines className="absolute inset-0 -z-10" />
        <div className="relative z-10 text-center">
          <h2 className="text-5xl font-bold">Floating Lines 背景</h2>
          <p className="mt-4 text-zinc-400">流动线条 · WebGPU/OGL 渲染</p>
        </div>
      </section>

      {/* 第三屏：SideRays 侧向光束 */}
      <section className="relative flex h-screen items-center justify-center overflow-hidden">
        <SideRays
          className="absolute inset-0 -z-10"
          speed={1.5}
          rayColor1="#8b5cf6"
          rayColor2="#06b6d4"
        />
        <div className="relative z-10 text-center">
          <h2 className="text-5xl font-bold">Side Rays 侧光</h2>
          <p className="mt-4 text-zinc-400">双色渐变光束 · 可调速度</p>
        </div>
      </section>
    </main>
  )
}
