// The compiled widget CSS is inlined as a string by esbuild's text loader.
declare module "*.generated.css" {
  const content: string;
  export default content;
}
