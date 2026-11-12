module Test.Main where

import Prelude
import Effect (Effect)
import Effect.Console (log)
import Main (answer)

foreign import fail :: Effect Unit

main :: Effect Unit
main = if answer == 42 then log "Spago assertion passed" else fail
