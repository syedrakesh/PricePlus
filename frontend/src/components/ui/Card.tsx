import styles from './Card.module.css';
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  glow?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = '', glow, onClick }: CardProps) {
  return (
    <div
      className={[styles.card, glow ? styles.glow : '', onClick ? styles.clickable : '', className].join(' ')}
      onClick={onClick}
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
