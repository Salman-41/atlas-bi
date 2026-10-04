import Image from "next/image";
export default function AtlasLogo() {
  return (
    <span className="brand-icon atlas-logo">
      <Image src="/atlas-mark.png" alt="" width={48} height={48} priority />
      <span className="sr-only">Atlas</span>
    </span>
  );
}
