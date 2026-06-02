/// <reference types="vite/client" />

// `plotly.js-dist-min` ships no types. We only ever touch it via
// dynamic `import('plotly.js-dist-min')` in PlotRenderer and pass the
// module through unchecked, so an `any`-shaped declaration is enough
// to silence the implicit-any error without pulling in @types/plotly.js.
declare module 'plotly.js-dist-min'
