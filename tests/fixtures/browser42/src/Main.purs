module Main where

import Prelude
import Effect (Effect)
import Effect.Console (log)

answer :: Int
answer = 20 + 22

main :: Effect Unit
main = log ("locked Spago: " <> show answer)
