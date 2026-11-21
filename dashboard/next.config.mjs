/** Exportación estática: el sitio queda en out/ y se publica en GitHub Pages. */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default { output: "export", basePath, images: { unoptimized: true }, trailingSlash: true };
