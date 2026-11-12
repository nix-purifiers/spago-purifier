module Projection.Answer (answer, render) where

import Prelude

foreign import offset :: Int -> Int

answer :: Int -> Int
answer input = offset input + 43

render :: Int -> String
render input = show (answer input)
