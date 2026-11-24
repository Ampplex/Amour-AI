import { Injectable, signal } from '@angular/core';

export type AlertType = 'info' | 'success' | 'warning' | 'danger';

export interface AlertButton {
  text: string;
  style?: 'default' | 'cancel' | 'destructive' | 'primary';
  onPress?: () => void;
}

export interface AlertConfig {
  title: string;
  message?: string;
  buttons?: AlertButton[];
  type?: AlertType;
}

@Injectable({
  providedIn: 'root'
})
export class AlertService {
  readonly alertConfig = signal<AlertConfig | null>(null);
  readonly isVisible = signal<boolean>(false);

  showAlert(title: string, message?: string, buttons?: AlertButton[], type?: AlertType): void {
    let resolvedType: AlertType = type || 'info';

    if (!type) {
      const lower = title.toLowerCase();
      const hasDestructive = buttons?.some(b => b.style === 'destructive');
      if (hasDestructive || lower.includes('delete') || lower.includes('remove') || lower.includes('sign out') || lower.includes('discard') || lower.includes('exit')) {
        resolvedType = 'danger';
      } else if (lower.includes('success') || lower.includes('saved') || lower.includes('activated')) {
        resolvedType = 'success';
      } else if (lower.includes('warning') || lower.includes('required') || lower.includes('attention')) {
        resolvedType = 'warning';
      }
    }

    const defaultButtons: AlertButton[] = buttons && buttons.length > 0 
      ? buttons 
      : [{ text: 'OK', style: 'primary', onPress: () => this.hideAlert() }];

    this.alertConfig.set({
      title,
      message,
      buttons: defaultButtons,
      type: resolvedType
    });
    this.isVisible.set(true);
  }

  hideAlert(): void {
    this.isVisible.set(false);
    setTimeout(() => {
      this.alertConfig.set(null);
    }, 200);
  }

  handleButtonClick(btn: AlertButton): void {
    this.hideAlert();
    if (btn.onPress) {
      btn.onPress();
    }
  }
}
