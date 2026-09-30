import { clsx } from 'clsx';
export function Card({className,...props}:React.ComponentProps<'section'>){return <section className={clsx('card',className)} {...props}/>}
