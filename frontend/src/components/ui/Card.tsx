import styles from './Card.module.css';
import { ReactNode, HTMLAttributes } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  className?: string;
  glow?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = '', glow, onClick, ...rest }: CardProps) {
  return (
    <div
      className={[styles.card, glow ? styles.glow : '', onClick ? styles.clickable : '', className].join(' ')}
      onClick={onClick}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={[styles.header, className].join(' ')}>{children}</div>;
}

export function CardBody({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={[styles.body, className].join(' ')}>{children}</div>;
}
