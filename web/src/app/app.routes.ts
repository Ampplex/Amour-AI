import { Routes } from '@angular/router';
import { StartScreenComponent } from './screens/start/start.component';
import { LoginScreenComponent } from './screens/login/login.component';
import { SignupScreenComponent } from './screens/signup/signup.component';
import { ForgotPasswordScreenComponent } from './screens/forgot-password/forgot-password.component';
import { TabsShellComponent } from './screens/tabs-shell/tabs-shell.component';
import { HomeScreenComponent } from './screens/tabs/home/home.component';
import { PersonasScreenComponent } from './screens/tabs/personas/personas.component';
import { ChatsScreenComponent } from './screens/tabs/chats/chats.component';
import { CreateScreenComponent } from './screens/tabs/create/create.component';
import { ProfileScreenComponent } from './screens/tabs/profile/profile.component';

export const routes: Routes = [
  { path: '', component: StartScreenComponent },
  { path: 'login', component: LoginScreenComponent },
  { path: 'signup', component: SignupScreenComponent },
  { path: 'forgot-password', component: ForgotPasswordScreenComponent },
  {
    path: 'tabs',
    component: TabsShellComponent,
    children: [
      { path: '', redirectTo: 'home', pathMatch: 'full' },
      { path: 'home', component: HomeScreenComponent },
      { path: 'personas', component: PersonasScreenComponent },
      { path: 'chats', component: ChatsScreenComponent },
      { path: 'create', component: CreateScreenComponent },
      { path: 'profile', component: ProfileScreenComponent },
    ]
  },
  { path: '**', redirectTo: '' }
];
