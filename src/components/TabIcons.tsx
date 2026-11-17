import React from 'react';
import Svg, { Path, Circle } from 'react-native-svg';

interface IconProps {
  color?: string | null | any;
  size?: number;
}

export function HomeIcon({ color = '#FFFFFF', size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3 10.2L12 3.2L21 10.2V19.8C21 20.4627 20.4627 21 19.8 21H4.2C3.53726 21 3 20.4627 3 19.8V10.2Z"
        stroke={color}
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M9 21V13.8C9 13.3582 9.35817 13 9.8 13H14.2C14.6418 13 15 13.3582 15 13.8V21"
        stroke={color}
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

export function PersonasIcon({ color = '#FFFFFF', size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle
        cx="10.5"
        cy="10.5"
        r="7.5"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <Path
        d="M16.2 16.2L21 21"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </Svg>
  );
}

export function PlusCircleIcon({ color = '#FFFFFF', size = 26 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="9.5" stroke={color} strokeWidth="2.1" />
      <Path
        d="M12 7.5V16.5M7.5 12H16.5"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

export function ChatsIcon({ color = '#FFFFFF', size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M20 12c0-4.418-3.582-8-8-8S4 7.582 4 12c0 1.63.487 3.148 1.325 4.415L4 20.5l4.318-1.233A7.95 7.95 0 0 0 12 20c4.418 0 8-3.582 8-8z"
        stroke={color}
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

export function ProfileIcon({ color = '#FFFFFF', size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="8" r="4.2" stroke={color} strokeWidth="2.1" />
      <Path
        d="M4.5 20.5c0-4.142 3.358-7.5 7.5-7.5s7.5 3.358 7.5 7.5"
        stroke={color}
        strokeWidth="2.1"
        strokeLinecap="round"
      />
    </Svg>
  );
}
