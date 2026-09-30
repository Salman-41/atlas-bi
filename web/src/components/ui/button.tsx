import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { clsx } from 'clsx';
// shadcn-style, locally owned primitive; semantic button behavior by default.
export function Button({ asChild=false, className, ...props }: React.ComponentProps<'button'> & {asChild?:boolean}) { const Comp=asChild?Slot:'button'; return <Comp className={clsx('button',className)} {...props}/>; }
