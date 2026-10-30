import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import ProfessionalAlertModal, {
  AlertConfig,
  AlertButton,
  AlertType,
} from '../components/ProfessionalAlertModal';

export { AlertButton, AlertType, AlertConfig };

interface AlertContextValue {
  showAlert: (
    title: string,
    message?: string,
    buttons?: AlertButton[],
    type?: AlertType
  ) => void;
  hideAlert: () => void;
}

const AlertContext = createContext<AlertContextValue>({
  showAlert: () => {},
  hideAlert: () => {},
});

// Global singleton bridge so `showAlert` can be called from anywhere without hook requirement
let globalAlertHandler:
  | ((
      title: string,
      message?: string,
      buttons?: AlertButton[],
      type?: AlertType
    ) => void)
  | null = null;

let globalHideHandler: (() => void) | null = null;

/**
 * Drop-in professional replacement for React Native's `Alert.alert`.
 * Completely built in React Native StyleSheet with OLED black theme, Changa One typography,
 * and zero emojis.
 */
export function showAlert(
  title: string,
  message?: string,
  buttons?: AlertButton[],
  type?: AlertType
) {
  if (globalAlertHandler) {
    globalAlertHandler(title, message, buttons, type);
  } else {
    console.warn('[AlertContext] showAlert called before AlertProvider was mounted');
  }
}

export function hideAlert() {
  if (globalHideHandler) {
    globalHideHandler();
  }
}

export function AlertProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AlertConfig | null>(null);
  const [visible, setVisible] = useState<boolean>(false);

  const handleHide = useCallback(() => {
    setVisible(false);
    setTimeout(() => {
      setConfig(null);
    }, 200);
  }, []);

  const handleShow = useCallback(
    (
      title: string,
      message?: string,
      buttons?: AlertButton[],
      type?: AlertType
    ) => {
      // Auto-infer type if not specified
      let resolvedType: AlertType = type || 'info';

      if (!type) {
        const lowerTitle = title.toLowerCase();
        const hasDestructive = buttons?.some((b) => b.style === 'destructive');

        if (hasDestructive || lowerTitle.includes('delete') || lowerTitle.includes('remove') || lowerTitle.includes('sign out') || lowerTitle.includes('discard') || lowerTitle.includes('exit')) {
          resolvedType = 'danger';
        } else if (lowerTitle.includes('activated') || lowerTitle.includes('success') || lowerTitle.includes('saved')) {
          resolvedType = 'success';
        } else if (lowerTitle.includes('permission') || lowerTitle.includes('required') || lowerTitle.includes('warning') || lowerTitle.includes('attention')) {
          resolvedType = 'warning';
        }
      }

      setConfig({
        title,
        message,
        buttons,
        type: resolvedType,
      });
      setVisible(true);
    },
    []
  );

  useEffect(() => {
    globalAlertHandler = handleShow;
    globalHideHandler = handleHide;
    return () => {
      globalAlertHandler = null;
      globalHideHandler = null;
    };
  }, [handleShow, handleHide]);

  return (
    <AlertContext.Provider value={{ showAlert: handleShow, hideAlert: handleHide }}>
      {children}
      <ProfessionalAlertModal
        visible={visible}
        config={config}
        onClose={handleHide}
      />
    </AlertContext.Provider>
  );
}

export function useAlert() {
  return useContext(AlertContext);
}
