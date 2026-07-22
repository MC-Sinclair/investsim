import styles from './LegalBanner.module.css'

export const LEGAL_DISCLAIMER =
  'Simulación educativa, no es asesoramiento financiero. Capital ficticio.'

export function LegalBanner() {
  return <div className={styles.banner}>{LEGAL_DISCLAIMER}</div>
}
