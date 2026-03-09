import { type ImmutableObject } from 'seamless-immutable'

export interface Config {
  apiUrl?: string
  idField?: string
}

export type IMConfig = ImmutableObject<Config>

